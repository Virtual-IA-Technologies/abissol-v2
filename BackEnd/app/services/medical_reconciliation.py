"""One ledger: existing vouchers, bank verification and frozen liquidation items."""
import hashlib
import re
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import case,func
from ..models.medical import MedicalVoucher as Voucher

PURPOSES={'deposit','commission_payment','commission_offset'}

def bank_identity(bank,account,reference,paid_on):
    bank=' '.join(bank.upper().split())
    account=re.sub(r'[\s-]','',account).upper()
    reference=' '.join(reference.upper().split())
    if len(bank)<2 or not re.fullmatch(r'[A-Z0-9]{6,34}',account) or len(reference)<3:
        raise HTTPException(422,'Indica banco, cuenta completa (6 a 34 caracteres) y número de operación')
    digest=hashlib.sha256('\x1f'.join([bank,account,paid_on.isoformat(),reference]).encode()).hexdigest()
    return bank,account,digest

def require_current(row):
    if row.legacy_id:raise HTTPException(409,'Histórico de consulta: no se modifica ni se concilia nuevamente')

def totals(db,ident):
    result={}
    for purpose,verified,amount in db.query(Voucher.purpose,Voucher.verified_at.is_not(None),func.sum(Voucher.amount)).filter_by(liquidation_id=ident,active=True).group_by(Voucher.purpose,Voucher.verified_at.is_not(None)):
        result[purpose+('_verified' if verified else '_pending')]=amount
    return result

def balance(row,values):
    def value(kind,suffix):return values.get(kind+'_'+suffix,Decimal(0)) or Decimal(0)
    deposit=value('deposit','verified');offset=value('commission_offset','verified');paid=value('commission_payment','verified')
    pending=sum((value(kind,'pending') for kind in PURPOSES),Decimal(0))
    result={'deposit_registered':deposit+value('deposit','pending'),'deposit_verified':deposit,
        'commission_paid':paid,'commission_offset':offset,'pending_verification':pending,
        'balance_due':row.deposit_required-deposit-offset,'commission_due':row.commission_total-paid-offset}
    result['commission_state']='historical' if row.legacy_id else 'not_applicable' if row.kind!='seller' else 'settled' if result['commission_due']==0 else 'partial' if paid+offset else 'pending'
    return {k:str(v) if isinstance(v,Decimal) else v for k,v in result.items()}

def aggregate():
    """One grouped join for a page, never one query per liquidation."""
    fields=[]
    for kind in PURPOSES:
        for verified in (True,False):
            condition=(Voucher.purpose==kind)&(Voucher.verified_at.is_not(None) if verified else Voucher.verified_at.is_(None))
            fields.append(func.sum(case((condition,Voucher.amount),else_=0)).label(kind+('_verified' if verified else '_pending')))
    return fields

async def register(db,request,user,row,reference,amount,paid_on,file,bank,account,purpose,note,*,commit=True,require_account=True):
    from ..routes import medical as m
    require_current(row)
    if row.kind=='seller' and row.status in {'submitted','approved'} and not m.admin(user):
        raise HTTPException(409,'Enviado a Oficina Principal: espera su revisión antes de cambiar el voucher')
    if purpose not in PURPOSES:raise HTTPException(422,'Tipo de movimiento no válido')
    if row.kind=='meta':raise HTTPException(422,'META utiliza su flujo mensual')
    if purpose!='deposit':
        m.ensure_option_access(db,user,'medical-liquidations','gestor');m.global_only(user)
        if row.kind!='seller':raise HTTPException(422,'Solo vendedores tienen pagos de comisión')
    allowed={'draft','observed','submitted','approved'} if purpose!='commission_payment' else {'approved','paid'}
    if row.status not in allowed:raise HTTPException(409,'El estado no permite este movimiento')
    if paid_on>m.datetime.now(m.ZoneInfo('America/Lima')).date():raise HTTPException(422,'La fecha no puede estar en el futuro')
    note=note.strip();reference=' '.join(reference.strip().split())
    if len(note)<5:raise HTTPException(422,'Describe el sustento del movimiento (mínimo cinco caracteres)')
    if purpose=='commission_offset':
        bank=account=None
        key=hashlib.sha256(f'offset:{row.id}:{reference.upper()}'.encode()).hexdigest()
    elif require_account:
        bank,account,key=bank_identity(bank,account,reference,paid_on)
    else:
        bank=' '.join(bank.upper().split());account=re.sub(r'[\s-]','',account).upper()
        if len(bank)<2 or len(reference)<3:raise HTTPException(422,'Indica banco y número de operación')
        key=hashlib.sha256('\x1f'.join([bank,paid_on.isoformat(),reference.upper()]).encode()).hexdigest()
    content=await file.read(5*1024*1024+1)
    if len(content)>5*1024*1024:raise HTTPException(413,'Máximo 5 MB por sustento')
    suffix='.pdf' if content.startswith(b'%PDF-') else '.png' if content.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if content.startswith(b'\xff\xd8\xff') else None
    if not suffix:raise HTTPException(422,'Adjunta PDF, PNG o JPEG')
    digest=hashlib.sha256(content).hexdigest()
    from sqlalchemy import and_,or_
    # Bankless historical entries remain ambiguous: never silently reuse them.
    duplicate=db.query(Voucher.id).filter(Voucher.active.is_(True),or_(Voucher.active_reference==key,Voucher.digest==digest,
        and_(func.upper(Voucher.bank)==bank,func.upper(Voucher.reference)==reference.upper(),Voucher.paid_on==paid_on),
        and_(Voucher.bank.is_(None),Voucher.purpose=='deposit',func.upper(Voucher.reference)==reference.upper()))).first()
    if duplicate:raise HTTPException(409,'Operación o archivo ya registrado; revisa su constancia anterior')
    values=totals(db,row.id)
    def committed(kind):return sum((values.get(kind+'_'+suffix,Decimal(0)) for suffix in ('pending','verified')),Decimal(0))
    if purpose in {'deposit','commission_offset'} and amount+committed('deposit')+committed('commission_offset')>row.deposit_required:
        raise HTTPException(422,'El movimiento supera el saldo por depositar; revisa los abonos registrados')
    if purpose!='deposit' and amount+committed('commission_payment')+committed('commission_offset')>row.commission_total:
        raise HTTPException(422,'El movimiento supera la comisión pendiente')
    m.STORAGE.mkdir(parents=True,exist_ok=True)
    storage_key=m.secrets.token_hex(24)+suffix;target=m.STORAGE/storage_key;target.write_bytes(content)
    # Persist the detected extension, not an arbitrary upload suffix.
    filename=m.Path(file.filename or 'constancia').stem[:170]+suffix
    voucher=Voucher(liquidation_id=row.id,reference=reference,active_reference=key,amount=amount,paid_on=paid_on,
        filename=filename,storage_key=storage_key,digest=digest,active_digest=digest,purpose=purpose,bank=bank,account=account,note=note)
    try:result=m.save(db,request,user,voucher,commit=commit)
    except Exception:target.unlink(missing_ok=True);raise
    return {k:v for k,v in result.items() if k not in {'storage_key','digest','active_digest','active_reference'}}
