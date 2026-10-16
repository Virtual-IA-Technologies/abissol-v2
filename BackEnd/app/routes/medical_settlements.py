"""Read-only seller statements and explicit administrative bank verification."""
from fastapi import APIRouter,Depends,Query,HTTPException,Request,Form,File,UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func,case,exists
from sqlalchemy.orm import Session
from decimal import Decimal
from ..database import get_db
from ..services.access_control import require_access
from ..services import medical_reconciliation as r
from ..schemas.medical import ReasonInput, SettlementApprovalInput
from ..utils.time import utc_now
from . import medical as m

router=APIRouter(prefix='/medical')

@router.get('/seller-pending')
def pending(responsible_id:int|None=None,db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations'))):
    own=m.profile(db,user)
    if not m.admin(user) and not own:raise HTTPException(403,'Tu perfil no prepara liquidaciones')
    query=m.scope(db,user).filter(m.Issuance.status=='issued',m.Issuance.payment_status.in_(['pending','collected_by_seller']))
    if responsible_id:
        m.find(m.settlement_profiles(db,user),responsible_id)
        query=query.filter(m.Issuance.responsible_id==responsible_id)
    used=db.query(m.Item.issuance_id).filter(m.Item.active_key.like('seller:%'))
    rows=query.filter(~m.Issuance.id.in_(used.scalar_subquery())).order_by(m.Issuance.id.desc()).limit(1000).all()
    from ..services.medical_testing import batch
    current_batch=batch(db)
    return {'items':[{**m.dump(e),'deposit':str(m.liquidation_amounts(e,'seller')[1]),
        'eligible':not e.test_batch or e.test_batch==current_batch} for e in rows]}

@router.post('/seller-settlements')
async def submit_selected(request:Request,responsible_id:int=Form(...),issuance_ids:str=Form(...),
    amount:Decimal=Form(...,gt=0,max_digits=12,decimal_places=2),reference:str=Form(...,min_length=3,max_length=100),
    paid_on:m.date=Form(...),bank:str=Form(...,min_length=2,max_length=80),account:str=Form('',max_length=34),
    note:str=Form('',max_length=1000),ocr_text:str=Form('',max_length=20000),file:UploadFile=File(...),
    db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations','editor'))):
    import json
    from types import SimpleNamespace
    from datetime import date
    from ..services.medical_settings import business_settings
    from ..services.email import get_smtp_setting,EmailNotConfigured
    from ..services.medical_settlement_delivery import KIND,deliver,office_recipients
    try:
        ids=json.loads(issuance_ids)
        if not isinstance(ids,list) or not 1<=len(ids)<=1000 or any(type(i)!=int or i<=0 for i in ids) or len(ids)!=len(set(ids)):raise ValueError()
    except (ValueError,TypeError):raise HTTPException(422,'Selecciona las emisiones pendientes')
    settings=business_settings(db)
    if not settings['settlement_office_email']:raise HTTPException(422,'Configura el correo de Oficina Principal')
    recipient=office_recipients(settings)
    if len(recipient)>180:raise HTTPException(422,'Los destinatarios de liquidaciones exceden 180 caracteres')
    try:get_smtp_setting(db)
    except EmailNotConfigured:raise HTTPException(422,'Configura el correo SMTP antes de enviar')
    payload=SimpleNamespace(kind='seller',responsible_id=responsible_id,starts_on=date(1900,1,1),ends_on=date(2100,1,1),issuance_ids=ids)
    selected=m.scope(db,user).filter(m.Issuance.id.in_(ids)).with_for_update().all()
    if len(selected)!=len(ids):raise HTTPException(404,'Selección fuera de tu ámbito comercial')
    batches={e.test_batch for e in selected}
    if len(batches)!=1:raise HTTPException(422,'No mezcles emisiones reales y de prueba en un voucher')
    test_batch=next(iter(batches))
    if test_batch:
        from ..services.medical_testing import batch
        if test_batch!=batch(db):raise HTTPException(409,'Este lote de prueba ya está cerrado')
    payload.test_batch=test_batch;payload.deposit_submission=True
    entries=m.liquidation_candidates(db,user,payload,lock=True)
    expected=sum((m.liquidation_amounts(e,'seller')[1] for e in entries),Decimal(0))
    if expected!=amount:raise HTTPException(422,f'El voucher debe coincidir con S/ {expected:.2f}')
    from ..schemas.medical import LiquidationInput
    payload=LiquidationInput(kind='seller',responsible_id=responsible_id,starts_on=min(e.sale_date for e in entries),ends_on=max(e.sale_date for e in entries),issuance_ids=ids)
    row=m.build_liquidation(db,user,payload,entries)
    if test_batch:row.code='PRUEBA-'+row.code
    # OCR is supporting evidence, never bank verification. Office confirms authenticity.
    row.notes=note.strip() or 'Emisiones y monto revisados por el responsable.'
    evidence=('Lectura OCR adjunta; pendiente de verificación bancaria.\n'+ocr_text[:700]) if ocr_text.strip() else 'Lectura manual confirmada; pendiente de verificación bancaria.'
    voucher=await r.register(db,request,user,row,reference,amount,paid_on,file,bank,account,'deposit',evidence,commit=False,require_account=False)
    target=m.STORAGE/db.get(m.Voucher,voucher['id']).storage_key
    try:
        row.status='submitted'
        dispatch=m.Dispatch(liquidation_id=row.id,kind=KIND,channel='email',recipient=recipient,status='simulated' if test_batch else 'queued',created_by=user.id)
        db.add(dispatch)
        m.save(db,request,user,row)
    except Exception:
        target.unlink(missing_ok=True);raise
    deliver(db,dispatch.id)
    return {'id':row.id,'code':row.code,'status':row.status,'notification_status':dispatch.status}

@router.post('/liquidations/{ident}/settle')
def settle(ident:int,payload:SettlementApprovalInput,request:Request,db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations','gestor'))):
    m.global_only(user)
    row=m.find(m.liquidation_scope(db,user),ident,True)
    allowed = {'submitted','approved'} | ({'pending'} if row.legacy_id else set())
    if row.kind!='seller' or row.status not in allowed:raise HTTPException(409,'La liquidación no está enviada para revisión')
    vouchers=db.query(m.Voucher).filter_by(liquidation_id=ident,active=True).with_for_update().all()
    deposits=sum((v.amount for v in vouchers if v.purpose in {'deposit','commission_offset'}),Decimal(0))
    if deposits!=row.deposit_required or not vouchers:raise HTTPException(422,'El voucher no coincide con las emisiones seleccionadas')
    items=db.query(m.Issuance).join(m.Item,m.Item.issuance_id==m.Issuance.id).filter(m.Item.liquidation_id==ident).all()
    if not items or any(e.status!='issued' for e in items):raise HTTPException(409,'Revisa las emisiones incluidas antes de aprobar')
    reason=payload.reason.strip() or "Aprobación de Oficina Principal"
    before=m.dump(row)
    for v in vouchers:
        if not v.verified_at:
            old=m.dump(v);v.verified_at=utc_now();v.verified_by=user.id
            m.audit_change(db,request,user,'medical_voucher_verification',v.id,before=old,after={**m.dump(v),'reason':reason},module='abissol_medical')
    row.status='paid'
    row.notes=(row.notes+'\nOficina Principal: '+reason).strip()
    ids=db.query(m.Item.issuance_id).filter_by(liquidation_id=ident)
    db.query(m.Issuance).filter(m.Issuance.id.in_(ids.scalar_subquery())).update({'payment_status':'settled'},synchronize_session=False)
    return m.save(db,request,user,row,before)

@router.post('/liquidations/{ident}/reopen')
def reopen(ident:int,payload:ReasonInput,request:Request,db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations','gestor'))):
    m.global_only(user)
    row=m.find(m.liquidation_scope(db,user),ident,True)
    r.require_current(row)
    if row.kind!='seller' or row.status!='paid':raise HTTPException(409,'Solo se puede revertir una liquidación de vendedor liquidada')
    reason=payload.reason.strip()
    if len(reason)<5:raise HTTPException(422,'Describe el motivo de la reversión')
    before=m.dump(row)
    vouchers=db.query(m.Voucher).filter_by(liquidation_id=ident,active=True).with_for_update().all()
    for v in vouchers:
        if v.purpose in {'deposit','commission_offset'} and v.verified_at:
            old=m.dump(v);v.verified_at=None;v.verified_by=None
            m.audit_change(db,request,user,'medical_voucher_reopen',v.id,before=old,after={**m.dump(v),'reason':reason},module='abissol_medical')
    entries=db.query(m.Issuance,m.Item.deposit).join(m.Item,m.Item.issuance_id==m.Issuance.id).filter(m.Item.liquidation_id==ident).with_for_update().all()
    for entry,deposit in entries:
        if entry.payment_status=='settled':
            old=m.dump(entry)
            entry.payment_status='collected_by_seller' if deposit>0 else 'paid_to_abissol'
            m.audit_change(db,request,user,'medical_issuance_reopen',entry.id,before=old,after=m.dump(entry),module='abissol_medical')
    row.status='submitted'
    row.notes=(row.notes+'\nReversión de Oficina Principal: '+reason).strip()
    return m.save(db,request,user,row,before)

@router.post('/vouchers/{ident}/verify')
def verify(ident:int,payload:ReasonInput,request:Request,db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations','gestor'))):
    m.global_only(user)
    voucher=m.find(db.query(m.Voucher),ident)
    row=m.find(m.liquidation_scope(db,user),voucher.liquidation_id,True)
    r.require_current(row);db.refresh(voucher)
    if not voucher.active or row.status=='cancelled' or (row.status=='paid' and voucher.purpose!='commission_payment'):raise HTTPException(409,'Movimiento no disponible para conciliación')
    if voucher.verified_at:raise HTTPException(409,'El movimiento ya está conciliado')
    if voucher.purpose!='commission_offset' and (not voucher.bank or not voucher.account):raise HTTPException(422,'Retira la constancia anterior y registra banco y cuenta antes de conciliar')
    before=m.dump(voucher)
    voucher.verified_at=utc_now();voucher.verified_by=user.id
    m.audit_change(db,request,user,'medical_voucher_verification',ident,after={'reason':payload.reason},module='abissol_medical')
    result=m.save(db,request,user,voucher,before)
    return {k:v for k,v in result.items() if k not in {'storage_key','digest','active_digest','active_reference'}}

@router.get('/seller-statements')
def statements(search:str=Query('',max_length=180),offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations'))):
    own=m.profile(db,user) if not m.admin(user) else None
    if not m.admin(user) and not own:raise HTTPException(403,'Tu perfil no tiene estado de cuenta de vendedor')
    query=m.settlement_profiles(db,user)
    if search:query=query.filter(m.Profile.display_name.contains(search))
    count=query.count();profiles=query.order_by(m.Profile.id).offset(offset).limit(limit).all();ids=[p.id for p in profiles]
    if not ids:return {'items':[],'total':count}
    E,L,V=m.Issuance,m.Liquidation,m.Voucher
    visible_emissions=m.scope(db,user).with_entities(E.id).scalar_subquery()
    visible_liquidations=m.liquidation_scope(db,user).with_entities(L.id).scalar_subquery()
    used=exists().where(m.Item.issuance_id==E.id,m.Item.active_key.like('seller:%'))
    available=(~used)&E.payment_status.in_(['collected_by_seller','paid_to_abissol','settled'])
    deposit=case((E.payment_status!='collected_by_seller',0),else_=E.price)
    sales={row.responsible_id:dict(row._mapping) for row in db.query(E.responsible_id,
        func.sum(E.price).label('sales'),func.sum(case((E.payment_status=='pending',E.price),else_=0)).label('uncollected'),
        func.sum(case((available,deposit),else_=0)).label('unliquidated_deposit'),
        func.sum(case((available,E.seller_commission),else_=0)).label('unliquidated_commission'))
        .join(m.Source,m.Source.id==E.source_id).filter(E.id.in_(visible_emissions),E.test_batch.is_(None),E.responsible_id.in_(ids),E.status=='issued').group_by(E.responsible_id)}
    grouped=db.query(V.liquidation_id,*r.aggregate()).join(L,L.id==V.liquidation_id).filter(L.id.in_(visible_liquidations),L.responsible_id.in_(ids),L.kind=='seller',L.legacy_id.is_(None),V.active.is_(True)).group_by(V.liquidation_id).subquery()
    z=lambda name:func.coalesce(getattr(grouped.c,name),0)
    native=(L.legacy_id.is_(None))&(L.status!='cancelled')&(~L.code.like('PRUEBA-%'))
    due=L.deposit_required-z('deposit_verified')-z('commission_offset_verified')
    commission=L.commission_total-z('commission_payment_verified')-z('commission_offset_verified')
    fields=[func.sum(case((native,expr),else_=0)).label(name) for name,expr in [
        ('balance_due',due),('commission_due',commission),('deposited',z('deposit_verified')),
        ('commission_paid',z('commission_payment_verified')),('commission_offset',z('commission_offset_verified')),
        ('pending_verification',sum((z(k+'_pending') for k in r.PURPOSES)))]]
    liqs={row.responsible_id:dict(row._mapping) for row in db.query(L.responsible_id,*fields,
        func.sum(case((L.legacy_id.is_not(None),1),else_=0)).label('historical_count'))
        .outerjoin(grouped,grouped.c.liquidation_id==L.id).filter(L.id.in_(visible_liquidations),L.responsible_id.in_(ids),L.kind=='seller').group_by(L.responsible_id)}
    items=[]
    for p in profiles:
        values={**sales.get(p.id,{}),**liqs.get(p.id,{})}
        fields=['sales','uncollected','unliquidated_deposit','unliquidated_commission','balance_due','commission_due','deposited','commission_paid','commission_offset','pending_verification']
        items.append({'id':p.id,'name':p.display_name or f'Vendedor {p.id}','historical_count':int(values.get('historical_count') or 0),**{name:str(values.get(name) or Decimal(0)) for name in fields}})
    return {'items':items,'total':count}

@router.get('/liquidations/{ident}/receipt')
def receipt(ident:int,db:Session=Depends(get_db),user=Depends(require_access('medical-liquidations'))):
    row=m.find(m.liquidation_scope(db,user),ident)
    from ..services.medical_documents import binding
    from ..models.documents import DocumentVersion
    from ..services.documents import file_path
    link=binding(db,'liquidation',ident,'closing-receipt')
    if not link:raise HTTPException(404,'No existe constancia de cierre V2')
    version=db.query(DocumentVersion).filter_by(document_id=link.document_id).order_by(DocumentVersion.number.desc()).first()
    return FileResponse(file_path(version.storage_key),filename=row.code+'-cierre.pdf',headers={'Cache-Control':'private, no-store'})
