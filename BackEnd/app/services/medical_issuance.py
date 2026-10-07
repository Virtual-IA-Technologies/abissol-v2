"""Shared sale rules for portal and authenticated external sources."""
import hashlib
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from ..models.medical import MedicalCoverageLock, MedicalIssuance, MedicalPlan, MedicalProfile, MedicalSource
from . import medical_billing as fiscal


def create_sale(db, payload, emitter, actor_id):
    from .medical_testing import batch
    test_batch=batch(db,lock=True)
    if db.info.get('medical_test_only') and not test_batch:
        raise HTTPException(409,'El modo de pruebas está cerrado')
    today = datetime.now(ZoneInfo("America/Lima")).date()
    if payload.starts_on <= today:
        raise HTTPException(422,"La vigencia debe comenzar desde mañana (hora de Lima)")
    source = db.get(MedicalSource,emitter.source_id)
    if not emitter.active or emitter.kind not in {"responsible","emitter"} or not source or not source.active:
        raise HTTPException(422,"Origen o emisor no disponible")
    responsible = db.query(MedicalProfile).filter_by(id=emitter.manager_id if emitter.kind=="emitter" else emitter.id,
        active=True,kind="responsible",source_id=emitter.source_id).first()
    if not responsible:
        raise HTTPException(422,"El emisor no tiene un responsable activo en su origen")
    digest = hashlib.sha256(((test_batch+':' if test_batch else '')+f"{payload.document_type}:{payload.document_number.upper()}").encode()).hexdigest()
    if not db.get(MedicalCoverageLock,digest):
        try:
            with db.begin_nested():
                db.add(MedicalCoverageLock(document_hash=digest))
                db.flush()
        except IntegrityError:
            pass  # Another transaction created the lock; serialize on that row.
    db.query(MedicalCoverageLock).filter_by(document_hash=digest).with_for_update().one()
    plan = db.query(MedicalPlan).filter_by(id=payload.plan_id,active=True).with_for_update().first()
    if not plan:
        raise HTTPException(422,"Plan no disponible")
    ends_on = payload.starts_on + timedelta(days=plan.validity_days-1)
    overlap = db.query(MedicalIssuance.id).filter(MedicalIssuance.document_type==payload.document_type,
        MedicalIssuance.test_batch==test_batch,
        MedicalIssuance.document_number==payload.document_number,MedicalIssuance.status!="cancelled",
        MedicalIssuance.starts_on<=ends_on,MedicalIssuance.ends_on>=payload.starts_on).with_for_update().first()
    if overlap:
        raise HTTPException(409,"El documento ya tiene un programa con vigencia superpuesta. Revisa la emisión existente.")
    commission = Decimal((emitter.commission_overrides or {}).get(str(plan.id),
        (responsible.commission_overrides or {}).get(str(plan.id),str(plan.seller_commission))))
    if source.kind=="afocat" and emitter.kind=="responsible":
        commission = Decimal(0)
    commission = commission.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    if commission < 0 or commission + plan.provider_cost + plan.platform_fee > plan.price:
        raise HTTPException(422,"La comisión configurada supera el margen del plan")
    if not test_batch:plan.counter += 1
    values = payload.model_dump()
    values.pop('billing',None)
    billing_preference=payload.billing.model_dump(mode='json') if payload.billing else None
    if payload.billing and payload.billing.invoice_type_code=='01' and payload.payment_status=='pending':
        if not payload.billing.due_date or payload.billing.due_date<=today:
            raise HTTPException(422,'La factura a crédito requiere una fecha de vencimiento posterior a hoy')
    values['billing_preference']=billing_preference
    values.update(code='PRUEBA-'+secrets.token_hex(10) if test_batch else f"{plan.prefix}-{plan.counter:06d}",token=secrets.token_urlsafe(32),test_batch=test_batch,
        plan_name=plan.name,source_id=source.id,responsible_id=responsible.id,sale_date=today,ends_on=ends_on,
        price=plan.price,provider_cost=plan.provider_cost,seller_commission=commission,platform_fee=plan.platform_fee,
        meta_commission=(plan.provider_cost*plan.meta_percent/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),
        conditions_url=plan.conditions_url,created_by=actor_id,paid_amount=plan.price if payload.payment_status!="pending" else Decimal(0))
    row=MedicalIssuance(**values)
    db.add(row)
    db.flush()
    fiscal.enqueue_boleta(db,row)
    return row
