"""Read-only seller statements and explicit administrative bank verification."""
from fastapi import APIRouter,Depends,Query,HTTPException,Request
from fastapi.responses import FileResponse
from sqlalchemy import func,case,exists
from sqlalchemy.orm import Session
from decimal import Decimal
from ..database import get_db
from ..services.access_control import require_access
from ..services import medical_reconciliation as r
from ..schemas.medical import ReasonInput
from ..utils.time import utc_now
from . import medical as m

router=APIRouter(prefix='/medical')

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
    if not m.admin(user) and (not own or own.kind=='emitter'):raise HTTPException(403,'Tu perfil no tiene estado de cuenta de vendedor')
    query=m.profiles_scope(db,user).filter(m.Profile.kind=='responsible')
    if search:query=query.filter(m.Profile.display_name.contains(search))
    count=query.count();profiles=query.order_by(m.Profile.id).offset(offset).limit(limit).all();ids=[p.id for p in profiles]
    if not ids:return {'items':[],'total':count}
    E,L,V=m.Issuance,m.Liquidation,m.Voucher
    used=exists().where(m.Item.issuance_id==E.id,m.Item.active_key.like('seller:%'))
    available=(~used)&E.payment_status.in_(['collected_by_seller','paid_to_abissol','settled'])
    deposit=case((E.payment_status!='collected_by_seller',0),(m.Source.kind=='afocat',E.provider_cost),else_=case((E.paid_amount>0,E.paid_amount),else_=E.price))
    sales={row.responsible_id:dict(row._mapping) for row in db.query(E.responsible_id,
        func.sum(E.price).label('sales'),func.sum(case((E.payment_status=='pending',E.price),else_=0)).label('uncollected'),
        func.sum(case((available,deposit),else_=0)).label('unliquidated_deposit'),
        func.sum(case((available,E.seller_commission),else_=0)).label('unliquidated_commission'))
        .join(m.Source,m.Source.id==E.source_id).filter(E.responsible_id.in_(ids),E.status=='issued').group_by(E.responsible_id)}
    grouped=db.query(V.liquidation_id,*r.aggregate()).join(L,L.id==V.liquidation_id).filter(L.responsible_id.in_(ids),L.kind=='seller',L.legacy_id.is_(None),V.active.is_(True)).group_by(V.liquidation_id).subquery()
    z=lambda name:func.coalesce(getattr(grouped.c,name),0)
    native=(L.legacy_id.is_(None))&(L.status!='cancelled')
    due=L.deposit_required-z('deposit_verified')-z('commission_offset_verified')
    commission=L.commission_total-z('commission_payment_verified')-z('commission_offset_verified')
    fields=[func.sum(case((native,expr),else_=0)).label(name) for name,expr in [
        ('balance_due',due),('commission_due',commission),('deposited',z('deposit_verified')),
        ('commission_paid',z('commission_payment_verified')),('commission_offset',z('commission_offset_verified')),
        ('pending_verification',sum((z(k+'_pending') for k in r.PURPOSES)))]]
    liqs={row.responsible_id:dict(row._mapping) for row in db.query(L.responsible_id,*fields,
        func.sum(case((L.legacy_id.is_not(None),1),else_=0)).label('historical_count'))
        .outerjoin(grouped,grouped.c.liquidation_id==L.id).filter(L.responsible_id.in_(ids),L.kind=='seller').group_by(L.responsible_id)}
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
