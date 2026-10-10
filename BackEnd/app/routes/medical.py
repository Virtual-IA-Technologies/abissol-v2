"""Operación comercial ABISSOL con permisos de menú y alcance por registro."""
import hashlib
import html
import json
import re
import secrets
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pymupdf as fitz
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response, HTMLResponse, JSONResponse
from sqlalchemy import false, func, or_, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Usuario, UsuarioRol
from ..models.legacy import LegacyRecord, LegacyFile, MedicalBillingConfiguration
from ..utils.secrets import decrypt_secret
from ..models.medical import (MedicalPlan as Plan, MedicalSource as Source, MedicalProfile as Profile,
    MedicalIssuance as Issuance, MedicalLiquidation as Liquidation, MedicalLiquidationItem as Item,
    MedicalVoucher as Voucher, MedicalInvoice as Invoice, MedicalDispatch as Dispatch)
from ..schemas.medical import (PlanInput, SourceInput, ProfileInput, IssuanceInput, PaymentInput,
    ReasonInput, LiquidationInput, InvoiceInput, DispatchInput)
from ..services.access_control import require_access, ensure_option_access
from ..services.email import send_email
from ..services.whatsapp import send_whatsapp
from ..services.commercial_roles import seed_commercial_roles, ROLE_NAMES
from ..services import medical_billing as fiscal
from ..services import medical_reconciliation as reconciliation
from ..services.sunat import FiscalError
from ..models.fiscal import FiscalJob
from ..schemas.fiscal import BillingConfigurationInput
from ..utils.jwt import get_current_identity
from .audit import audit_change

router = APIRouter(prefix="/medical")
STORAGE = Path(__file__).resolve().parents[2] / "storage" / "medical"


def dump(row):
    # Decimal convertido a texto para no perder precisión en auditoría/JSON.
    result = {c.name: str(getattr(row, c.name)) if isinstance(getattr(row, c.name), Decimal)
            else jsonable_encoder(getattr(row, c.name)) for c in row.__table__.columns if c.name not in {'details'}}
    if isinstance(row, Invoice):
        result['fiscal_environment'] = (row.details or {}).get('environment', 'production' if row.legacy_id else None)
    return result


def admin(user):
    return any(r.es_superusuario or r.nombre == "Administrador" for r in user.active_roles())


def profile(db, user):
    return db.query(Profile).join(Source, Source.id == Profile.source_id).filter(Profile.user_id == user.id, Profile.active.is_(True), Source.active.is_(True)).first()


def profiles_scope(db, user):
    query = db.query(Profile)
    if admin(user):
        return query
    own = profile(db, user)
    if not own:
        return query.filter(false())
    if own.kind == "source_admin":
        return query.filter(Profile.source_id == own.source_id)
    return query.filter(or_(Profile.id == own.id, Profile.manager_id == own.id))


def scope(db, user):
    query = db.query(Issuance)
    if admin(user):
        return query
    own = profile(db, user)
    if not own:
        return query.filter(false())
    if own.kind == "source_admin":
        return query.filter(Issuance.source_id == own.source_id)
    if own.kind == "responsible":
        return query.filter(Issuance.responsible_id == own.id)
    return query.filter(Issuance.emitter_id == own.id)


def find(query, ident, lock=False):
    if lock:
        query = query.with_for_update()
    row = query.filter(query.column_descriptions[0]["entity"].id == ident).first()
    if row is None:
        raise HTTPException(404, "Registro no encontrado en tu ámbito comercial")
    return row


def save(db, request, user, row, before=None):
    try:
        db.add(row)
        db.flush()
        from ..services import medical_documents as archive
        if isinstance(row,Issuance):archive.emission(db,row,user.id)
        if isinstance(row,Voucher):archive.voucher(db,row,user.id)
        if isinstance(row,Liquidation) and row.status=='paid' and before and before.get('status')!='paid':
            archive.closing_receipt(db,row,user.id)
        if isinstance(row,Liquidation) and row.kind=='meta' and before is None:
            entries=db.query(Issuance).join(Item,Item.issuance_id==Issuance.id).filter(Item.liquidation_id==row.id).order_by(Issuance.id).all()
            if entries:archive.monthly(db,row,entries,user.id)
        audit_change(db, request, user, row.__tablename__, row.id, before=before, after=dump(row), module="abissol_medical")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "El código, referencia o registro ya existe; actualiza la lista") from exc
    except Exception:
        db.rollback()
        raise
    return dump(row)


def page(query, offset, limit):
    entity = query.column_descriptions[0]["entity"]
    total = query.count()
    return {"items": [dump(row) for row in query.order_by(entity.id.desc()).offset(offset).limit(limit)], "total": total}


@router.get("/lookups")
def lookups(section: str, db: Session = Depends(get_db), identity=Depends(get_current_identity)):
    if section not in {"plans", "network", "emissions", "dispatches", "liquidations", "billing", "reports"}:
        raise HTTPException(404)
    user = identity.effective_user
    ensure_option_access(db, user, "medical-" + section)
    needs_people = section in {"network", "emissions", "liquidations"}
    people = profiles_scope(db, user).all() if needs_people else []
    sources = []
    if section == "network":
        query = db.query(Source)
        if not admin(user):
            query = query.filter(Source.id.in_({p.source_id for p in people}))
        sources = query.order_by(Source.name).all()
    users = []
    if needs_people:
        query = db.query(Usuario).options(selectinload(Usuario.roles), selectinload(Usuario.role_assignments).selectinload(UsuarioRol.rol)).filter(Usuario.deleted_at.is_(None))
        if section != "network" or not admin(user):
            query = query.filter(Usuario.id.in_({p.user_id for p in people if p.user_id}))
        users = query.all()
    fiscal_config=fiscal.configuration(db)[1]
    return {"test_batch":fiscal_config.get("test_batch"),"plans": [dump(p) for p in db.query(Plan).order_by(Plan.name)] if section == "emissions" else [],
            "sources": [dump(source) for source in sources], "profiles": [dump(p) for p in people],
            "users": [{"id": u.id, "name": f"{u.nombre} {u.apellido or ''}".strip(), "is_active": u.is_active, "roles": [r.nombre for r in u.active_roles()]} for u in users],
            "emissions": [], "global_access": admin(user),
            "fiscal_enabled": bool(fiscal_config.get('enabled_in_v2')) if section == "billing" else False,
            "can_configure_communications": fiscal.programmer(user), "can_configure_billing": fiscal.programmer(user)}



@router.get("/plans")
def plans(db: Session = Depends(get_db), user=Depends(require_access("medical-plans"))):
    rows = db.query(Plan).order_by(Plan.id).all()
    return {"items": [dump(p) for p in rows], "total": len(rows)}


@router.get("/issuance-options")
def issuance_options(section: str, search: str = Query("", max_length=180), selected: int | None = None,
                     db: Session = Depends(get_db), identity=Depends(get_current_identity)):
    if section not in {"billing", "dispatches"}:
        raise HTTPException(404)
    user = identity.effective_user
    ensure_option_access(db, user, "medical-" + section)
    query = filtered(scope(db, user).filter(Issuance.status == "issued"), search, None, None)
    rows = query.order_by(Issuance.id.desc()).limit(50).all()
    if selected and not any(r.id == selected for r in rows):
        row = scope(db, user).filter(Issuance.id == selected).first()
        if row:
            rows.insert(0, row)
    return [{"value": str(r.id), "label": f"{r.code} · {r.customer}"} for r in rows]


@router.post("/plans")
def create_plan(payload: PlanInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-plans", "gestor"))):
    return save(db, request, user, Plan(**payload.model_dump()))


@router.put("/plans/{ident}")
def update_plan(ident: int, payload: PlanInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-plans", "gestor"))):
    row = find(db.query(Plan), ident, True)
    before = dump(row)
    if row.counter and payload.prefix != row.prefix:
        raise HTTPException(409, "Una serie utilizada no puede cambiar de prefijo")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    return save(db, request, user, row, before)


@router.get("/network")
def network(db: Session = Depends(get_db), user=Depends(require_access("medical-network"))):
    rows = profiles_scope(db, user).order_by(Profile.id).all()
    return {"items": [dump(p) for p in rows], "total": len(rows)}


def global_only(user):
    if not admin(user):
        raise HTTPException(403, "Solo administración puede modificar la red comercial")


@router.post("/sources")
def create_source(payload: SourceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-network", "gestor"))):
    global_only(user)
    if payload.kind == "internal" and payload.external_key:
        raise HTTPException(422, "Un origen interno no utiliza clave de integración externa")
    return save(db, request, user, Source(**payload.model_dump()))


@router.put("/sources/{ident}")
def update_source(ident: int, payload: SourceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-network", "gestor"))):
    global_only(user)
    row = find(db.query(Source), ident, True)
    before = dump(row)
    if (row.kind != payload.kind or row.external_key != payload.external_key) and db.query(Profile.id).filter_by(source_id=ident).first():
        raise HTTPException(409, "El origen ya tiene participantes; su tipo y clave externa identifican vínculos históricos")
    if payload.kind == "internal" and payload.external_key:
        raise HTTPException(422, "Un origen interno no utiliza clave de integración externa")
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    return save(db, request, user, row, before)


def validate_profile(db, payload, ident=None):
    account = find(db.query(Usuario).filter(Usuario.deleted_at.is_(None)), payload.user_id) if payload.user_id else None
    source = find(db.query(Source).filter_by(active=True), payload.source_id)
    if not payload.display_name:
        if not account:
            raise HTTPException(422, "Indica el nombre del participante externo")
        payload.display_name = f"{account.nombre} {account.apellido or ''}".strip()
    if source.kind == "internal" and (not account or payload.external_user_id):
        raise HTTPException(422, "Un participante interno requiere cuenta ABISSOL y no lleva ID externo")
    if payload.external_user_id and not source.external_key:
        raise HTTPException(422, "Configura la clave externa del origen antes de vincular identificadores")
    if not account and not payload.external_user_id:
        raise HTTPException(422, "Un participante sin cuenta requiere su identificador en la plataforma externa")
    if payload.apply_role and not account:
        raise HTTPException(422, "Los permisos se asignan a una cuenta de acceso; desmarca la asignación de rol")
    if payload.kind == "emitter":
        manager = find(db.query(Profile).filter_by(active=True, kind="responsible", source_id=payload.source_id), payload.manager_id)
        if manager.id == ident:
            raise HTTPException(422, "El emisor no puede ser su propio responsable")
    elif payload.manager_id is not None:
        raise HTTPException(422, "Solo un emisor depende de un responsable")


def apply_commercial_role(db, payload, request, actor):
    if not payload.apply_role:
        return
    account = db.get(Usuario, payload.user_id)
    before = {"roles": [r.nombre for r in account.roles]}
    roles = seed_commercial_roles(db)
    account.roles = [r for r in account.roles if r.nombre not in ROLE_NAMES.values()] + [roles[payload.kind]]
    audit_change(db, request, actor, "commercial_account_roles", account.id, before=before,
        after={"roles": [r.nombre for r in account.roles]}, module="abissol_medical",
        detail="Asignación explícita de rol comercial; se conservan roles de plataforma y accesos individuales.")


@router.post("/profiles")
def create_profile(payload: ProfileInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-network", "gestor"))):
    global_only(user)
    validate_profile(db, payload)
    apply_commercial_role(db, payload, request, user)
    return save(db, request, user, Profile(**payload.model_dump(exclude={"apply_role"})))


@router.put("/profiles/{ident}")
def update_profile(ident: int, payload: ProfileInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-network", "gestor"))):
    global_only(user)
    row = find(db.query(Profile), ident, True)
    before = dump(row)
    validate_profile(db, payload, ident)
    if any(getattr(row, k) != getattr(payload, k) for k in ("source_id", "kind", "manager_id", "external_user_id")) and (
        db.query(Issuance.id).filter(or_(Issuance.emitter_id == ident, Issuance.responsible_id == ident)).first()
        or db.query(Profile.id).filter_by(manager_id=ident).first()
    ):
        raise HTTPException(409, "Este perfil ya tiene emisiones o emisores; conserva su estructura y usa activo/inactivo")
    if row.user_id and row.user_id != payload.user_id:
        raise HTTPException(409, "La cuenta vinculada identifica al participante; no puede transferirse a otra persona")
    apply_commercial_role(db, payload, request, user)
    for k, v in payload.model_dump(exclude={"apply_role"}).items():
        setattr(row, k, v)
    return save(db, request, user, row, before)


def filtered(query, search, starts_on, ends_on):
    if starts_on and ends_on and starts_on > ends_on:
        raise HTTPException(422, "El rango de fechas está invertido")
    if search:
        term = "%" + search.replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(Issuance.code.ilike(term), Issuance.customer.ilike(term), Issuance.document_number.ilike(term)))
    if starts_on:
        query = query.filter(Issuance.sale_date >= starts_on)
    if ends_on:
        query = query.filter(Issuance.sale_date <= ends_on)
    return query


@router.get("/emissions")
def emissions(search: str = Query("", max_length=180), starts_on: date | None = None, ends_on: date | None = None,
              offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), state: str = "all", db: Session = Depends(get_db), user=Depends(require_access("medical-emissions"))):
    query = filtered(scope(db, user), search, starts_on, ends_on)
    today = datetime.now(ZoneInfo("America/Lima")).date()
    states = {"active": (Issuance.status == "issued") & (Issuance.starts_on <= today) & (Issuance.ends_on >= today),
              "upcoming": (Issuance.status == "issued") & (Issuance.starts_on > today),
              "expired": (Issuance.status == "issued") & (Issuance.ends_on < today), "cancelled": Issuance.status == "cancelled"}
    if state != "all" and state not in states:
        raise HTTPException(422, "Estado de vigencia inválido")
    counts = query.with_entities(func.count(Issuance.id), *[func.sum(case((condition, 1), else_=0)) for condition in states.values()]).one()
    summary = dict(zip(["all", *states], [int(value or 0) for value in counts]))
    return {**page(query.filter(states[state]) if state != "all" else query, offset, limit), "summary": summary}


@router.post("/emissions")
def create_emission(payload: IssuanceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions", "editor"))):
    if payload.payment_status == "paid_to_abissol" and not admin(user):
        raise HTTPException(403, "Administración debe confirmar los ingresos a ABISSOL")
    emitter = find(profiles_scope(db, user).filter(Profile.active.is_(True)), payload.emitter_id)
    if emitter.user_id is None:
        raise HTTPException(422, "Este participante es externo sin acceso al portal; sus emisiones deben ingresar por su integración")
    if payload.external_source or payload.external_reference:
        raise HTTPException(422, "El portal registra emisiones directas. La identidad de integración se valida por un conector externo autenticado")
    from ..services.medical_issuance import create_sale
    row = create_sale(db, payload, emitter, user.id)
    return save(db, request, user, row)


@router.post("/emissions/{ident}/payment")
def record_payment(ident: int, payload: PaymentInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions", "editor"))):
    row = find(scope(db, user), ident, True)
    if row.status != "issued" or row.payment_status != "pending":
        raise HTTPException(409, "Solo se puede confirmar una emisión vigente pendiente de pago")
    if payload.payment_status == "paid_to_abissol" and not admin(user):
        raise HTTPException(403, "Administración debe confirmar los ingresos a ABISSOL")
    if row.payment_method == "online" and payload.payment_status == "collected_by_seller":
        raise HTTPException(422, "El pago en línea debe confirmarse como ingreso a ABISSOL")
    before = dump(row)
    row.payment_status = payload.payment_status
    row.paid_amount = row.price
    fiscal.enqueue_boleta(db, row)
    audit_change(db, request, user, "medical_payments", row.id, after={"reference": payload.reference, "amount": str(row.price), "destination": payload.payment_status}, module="abissol_medical")
    return save(db, request, user, row, before)


@router.post("/emissions/{ident}/cancel")
def cancel_emission(ident: int, payload: ReasonInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions", "gestor"))):
    row = find(scope(db, user), ident, True)
    if row.status != "issued" or db.query(Item.id).filter(Item.issuance_id == ident, Item.active_key.is_not(None)).first() or db.query(Invoice.id).filter_by(issuance_id=ident).first():
        raise HTTPException(409, "No se puede anular: estado inválido, liquidación activa o documento de facturación vinculado")
    if row.paid_amount:
        raise HTTPException(409, "La emisión tiene un cobro: requiere conciliación y devolución antes de anular")
    before = dump(row)
    row.status, row.cancellation_reason = "cancelled", payload.reason
    return save(db, request, user, row, before)


def public_url(request, row):
    from ..services.medical_public_links import verification_url
    return verification_url(row)


def letter_pdf(row, url):
    from ..services.medical_rendering import welcome
    return welcome(row,url)


@router.get("/emissions/{ident}/letter")
def letter(ident: int, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions"))):
    row = find(scope(db, user), ident)
    from ..services.medical_information import letter_file
    archived=letter_file(db,row)
    if archived:return FileResponse(archived[0],filename=archived[1],media_type=archived[2],headers={'Cache-Control':'no-store'})
    return Response(letter_pdf(row,public_url(request,row)),media_type='application/pdf',headers={'Cache-Control':'no-store'})


@router.get("/validate/{token}")
def validate(token: str, request: Request, db: Session = Depends(get_db)):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43,64}', token):
        raise HTTPException(404, "Certificado no encontrado")
    row = db.query(Issuance).filter_by(token=token).first()
    if not row:
        raise HTTPException(404, "Certificado no encontrado")
    today = datetime.now(ZoneInfo("America/Lima")).date()
    valid = not row.test_batch and row.status == "issued" and row.starts_on <= today <= row.ends_on
    if "text/html" in request.headers.get("accept", ""):
        from .medical_public import validation_page
        return validation_page(db,row)
    return JSONResponse(jsonable_encoder({"organization": "ABISSOL", "certificate": row.code, "plan": row.plan_name,
            "starts_on": row.starts_on, "ends_on": row.ends_on, "status": row.status,
            "is_test":bool(row.test_batch), "valid_now": valid}), headers={"Cache-Control": "no-store"})


def liquidation_scope(db, user):
    query = db.query(Liquidation)
    if admin(user):
        return query
    own = profile(db, user)
    if not own or own.kind == "emitter":
        return query.filter(false())
    return query.filter(Liquidation.kind == "seller", Liquidation.responsible_id.in_(profiles_scope(db, user).with_entities(Profile.id).scalar_subquery()))


def liquidation_candidates(db, user, payload, lock=False):
    own = profile(db, user)
    if not admin(user) and (not own or own.kind == "emitter" or payload.kind != "seller"):
        raise HTTPException(403, "Tu perfil no puede preparar esta liquidación")
    if payload.kind == "seller":
        find(profiles_scope(db, user).filter(Profile.kind == "responsible"), payload.responsible_id)
    eligible = scope(db, user).filter(Issuance.test_batch.is_(None), Issuance.status == "issued", Issuance.sale_date >= payload.starts_on, Issuance.sale_date <= payload.ends_on)
    if payload.kind == "seller":
        eligible = eligible.filter(Issuance.responsible_id == payload.responsible_id, Issuance.payment_status.in_(["collected_by_seller", "paid_to_abissol", "settled"]))
    used = db.query(Item.issuance_id).filter(Item.active_key.like(payload.kind + ":%"))
    eligible = eligible.filter(~Issuance.id.in_(used.scalar_subquery()))
    if payload.issuance_ids is not None:
        eligible = eligible.filter(Issuance.id.in_(payload.issuance_ids))
    eligible = eligible.order_by(Issuance.id)
    rows = (eligible.with_for_update() if lock else eligible).limit(1001).all()
    if len(rows) > 1000:
        raise HTTPException(422, "Reduce el período: máximo 1000 emisiones por liquidación")
    if payload.issuance_ids and len(rows) != len(set(payload.issuance_ids)):
        raise HTTPException(409, "La selección contiene emisiones no disponibles; actualiza la vista previa")
    return rows


def afocat_emissions(db, emissions, kind):
    if kind != "seller":
        return set()
    ids = {e.id for e in emissions}
    return {ident for ident, in db.query(Issuance.id).join(Profile, Profile.id == Issuance.responsible_id).join(Source, Source.id == Issuance.source_id).filter(Issuance.id.in_(ids), Profile.kind == "responsible", Source.kind == "afocat")}


def liquidation_amounts(emission, kind, afocat_ids):
    commission = emission.seller_commission if kind == "seller" else emission.meta_commission if kind == "meta" else emission.platform_fee
    deposit = commission if kind != "seller" else Decimal(0)
    if kind == "seller" and emission.payment_status == "collected_by_seller":
        afocat_managed = emission.id in afocat_ids
        deposit = emission.provider_cost if afocat_managed else (emission.paid_amount or emission.price)
    return commission, deposit


@router.get("/liquidations")
def liquidations(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), kind: str | None = None,
                 search: str = Query("", max_length=180), status: str | None = None, starts_on: date | None = None, ends_on: date | None = None,
                 db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations"))):
    query = liquidation_scope(db, user)
    if kind:
        if kind not in {"seller", "meta", "platform"}: raise HTTPException(422, "Tipo de liquidación inválido")
        query = query.filter(Liquidation.kind == kind)
    if status: query = query.filter(Liquidation.status == status)
    if search: query = query.filter(or_(Liquidation.code.contains(search), Liquidation.notes.contains(search)))
    if starts_on: query = query.filter(Liquidation.ends_on >= starts_on)
    if ends_on: query = query.filter(Liquidation.starts_on <= ends_on)
    result=page(query, offset, limit)
    ids=[r['id'] for r in result['items']]
    totals={r.liquidation_id:dict(r._mapping) for r in db.query(Voucher.liquidation_id,*reconciliation.aggregate()).filter(Voucher.liquidation_id.in_(ids),Voucher.active.is_(True)).group_by(Voucher.liquidation_id)} if ids else {}
    from types import SimpleNamespace
    for item in result['items']:
        row=SimpleNamespace(**{**item,'deposit_required':Decimal(item['deposit_required']),'commission_total':Decimal(item['commission_total'])})
        item.update(reconciliation.balance(row,totals.get(item['id'],{})))
    return result


@router.post("/liquidations/preview")
def preview_liquidation(payload: LiquidationInput, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    rows = liquidation_candidates(db, user, payload)
    items = []
    afocat_ids = afocat_emissions(db, rows, payload.kind)
    for e in rows:
        commission, deposit = liquidation_amounts(e, payload.kind, afocat_ids)
        items.append({**dump(e), "commission": str(commission), "deposit": str(deposit)})
    return {"items": items, "total": len(items), "sale_total": str(sum((e.price for e in rows), Decimal(0))),
            "deposit_total": str(sum((Decimal(i["deposit"]) for i in items), Decimal(0)))}


@router.post("/liquidations")
def create_liquidation(payload: LiquidationInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    eligible = liquidation_candidates(db, user, payload, lock=True)
    if not eligible:
        raise HTTPException(422, "No hay emisiones disponibles en este período")
    row = Liquidation(**payload.model_dump(exclude={"issuance_ids"}), created_by=user.id, sales_total=0, commission_total=0, deposit_required=0)
    db.add(row)
    db.flush()
    prefix = {"seller": "LQ", "meta": "LM", "platform": "LP"}[payload.kind]
    row.code = f"{prefix}-{payload.starts_on:%Y%m%d}-{payload.ends_on:%Y%m%d}-{row.id:06d}"
    afocat_ids = afocat_emissions(db, eligible, payload.kind)
    for emission in eligible:
        commission, deposit = liquidation_amounts(emission, payload.kind, afocat_ids)
        db.add(Item(liquidation_id=row.id, issuance_id=emission.id, active_key=f"{payload.kind}:{emission.id}", sale=emission.price, commission=commission, deposit=deposit))
        row.sales_total += emission.price
        row.commission_total += commission
        row.deposit_required += deposit
    return save(db, request, user, row)


@router.get("/liquidations/{ident}")
def liquidation_detail(ident: int, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations"))):
    row = find(liquidation_scope(db, user), ident)
    result = dump(row)
    result["items"] = [{**dump(i), "code": e.code, "customer": e.customer, "document_number": e.document_number, "plan_name": e.plan_name} for i, e in db.query(Item, Issuance).join(Issuance, Issuance.id == Item.issuance_id).filter(Item.liquidation_id == ident)]
    result["vouchers"] = [{k: v for k, v in dump(i).items() if k not in {"storage_key", "digest", "active_digest", "active_reference"}} for i in db.query(Voucher).filter_by(liquidation_id=ident, active=True)]
    values={}
    for voucher in result['vouchers']:
        key=voucher['purpose']+('_verified' if voucher['verified_at'] else '_pending')
        values[key]=values.get(key,Decimal(0))+Decimal(voucher['amount'])
    result.update(reconciliation.balance(row,values))
    result['voucher_total']=result['deposit_registered']
    return result


@router.post("/liquidations/{ident}/vouchers")
async def add_voucher(ident: int, request: Request, reference: str = Form(..., min_length=3, max_length=100), amount: Decimal = Form(..., gt=0, max_digits=12, decimal_places=2), paid_on: date = Form(...), file: UploadFile = File(...), bank: str = Form('', max_length=80), account: str = Form('', max_length=34), purpose: str = Form('deposit', max_length=24), note: str = Form('', max_length=1000), db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    row = find(liquidation_scope(db, user), ident, True)
    return await reconciliation.register(db,request,user,row,reference,amount,paid_on,file,bank,account,purpose,note)


@router.post("/vouchers/{ident}/void")
def void_voucher(ident: int, payload: ReasonInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    row = find(db.query(Voucher).filter_by(active=True), ident)
    liquidation = find(liquidation_scope(db, user), row.liquidation_id, True)
    reconciliation.require_current(liquidation)
    db.refresh(row)
    if not row.active:raise HTTPException(409,'El movimiento ya fue retirado')
    if row.verified_at or row.purpose!='deposit':
        ensure_option_access(db,user,'medical-liquidations','gestor');global_only(user)
    if liquidation.status=='cancelled' or (liquidation.status=='paid' and (row.purpose!='commission_payment' or row.verified_at)):
        raise HTTPException(409,'Una liquidación cerrada conserva sus movimientos; requiere ajuste posterior')
    before = dump(row)
    row.active, row.active_digest, row.active_reference = False, None, None
    audit_change(db, request, user, "medical_voucher_void", row.id, after={"reason": payload.reason}, module="abissol_medical")
    save(db, request, user, row, before)
    return {"id": ident, "status": "voided"}


@router.get("/vouchers/{ident}/file")
def voucher_file(ident: int, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations"))):
    row = find(db.query(Voucher), ident)
    find(liquidation_scope(db, user), row.liquidation_id)
    path = STORAGE / row.storage_key
    if not path.is_file():
        raise HTTPException(404, "Archivo no disponible")
    return FileResponse(path, filename=row.filename, headers={"Cache-Control": "no-store"})


@router.post("/liquidations/{ident}/{action}")
def liquidation_action(ident: int, action: str, payload: ReasonInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    row = find(liquidation_scope(db, user), ident, True)
    if row.legacy_id:
        raise HTTPException(409, "Liquidación histórica: conserva su conciliación original")
    before = dump(row)
    transitions = {"submit": ({"draft", "observed"}, "submitted"), "approve": ({"submitted"}, "approved"),
                   "observe": ({"submitted"}, "observed"), "pay": ({"approved"}, "paid"), "cancel": ({"draft", "observed"}, "cancelled")}
    if action not in transitions or row.status not in transitions[action][0]:
        raise HTTPException(409, "La acción no corresponde al estado actual")
    if action in {"approve", "observe", "pay"}:
        ensure_option_access(db, user, "medical-liquidations", "gestor")
        global_only(user)
    amounts=reconciliation.balance(row,reconciliation.totals(db,ident))
    if action=='pay' and (Decimal(amounts['balance_due'])!=0 or Decimal(amounts['pending_verification'])!=0):
        raise HTTPException(422,'Para cerrar, concilia todos los movimientos y completa el saldo del depósito')
    if action=='cancel' and db.query(Voucher.id).filter_by(liquidation_id=ident,active=True).first():
        raise HTTPException(409,'Retira y revisa los movimientos antes de cancelar; no se liberan depósitos automáticamente')
    row.status, row.notes = transitions[action][1], payload.reason
    if action == "cancel":
        db.query(Item).filter_by(liquidation_id=ident).update({"active_key": None})
        db.query(Voucher).filter_by(liquidation_id=ident).update({"active": False, "active_digest": None, "active_reference": None})
    if action == "pay" and row.kind == "seller":
        ids = db.query(Item.issuance_id).filter_by(liquidation_id=ident)
        db.query(Issuance).filter(Issuance.id.in_(ids.scalar_subquery())).update({"payment_status": "settled"}, synchronize_session=False)
    return save(db, request, user, row, before)


@router.get("/billing")
def billing(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user=Depends(require_access("medical-billing"))):
    return page(invoice_scope(db, user), offset, limit)


def invoice_scope(db, user):
    query = db.query(Invoice)
    return query if admin(user) else query.filter(Invoice.deleted_at.is_(None), Invoice.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery()))


def legacy_data(db, table, ident):
    record = db.query(LegacyRecord).filter_by(source_table=table, source_key=str(ident)).first()
    return json.loads(decrypt_secret(record.payload_encrypted)) if record else {}


def legacy_download(db, source_path=None, *, file_id=None, filename=None):
    file = db.get(LegacyFile, file_id) if file_id else db.query(LegacyFile).filter_by(path_hash=hashlib.sha256(str(source_path).replace('\\', '/').encode()).hexdigest()).first() if source_path else None
    if not file:
        raise HTTPException(404, "El archivo original no está disponible en el archivo migrado")
    root = STORAGE.parent / 'legacy_abissol'
    path = (root / file.storage_key).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise HTTPException(404, "Archivo original no disponible")
    return FileResponse(path, filename=filename or file.filename, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get('/billing/configuration')
def billing_configuration(db: Session = Depends(get_db), user=Depends(require_access('medical-billing', 'gestor'))):
    if not fiscal.programmer(user):
        raise HTTPException(403, 'Solo el rol Programador puede acceder a la configuración fiscal')
    return fiscal.public_configuration(db)


@router.put('/billing/configuration')
def update_billing_configuration(payload: BillingConfigurationInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access('medical-billing', 'gestor'))):
    if not fiscal.programmer(user):
        raise HTTPException(403, 'Solo el rol Programador puede modificar la configuración fiscal')
    row, raw = fiscal.configuration(db, lock=True)
    if not row:
        raise HTTPException(422,'Primero importa la configuración fiscal y su certificado.')
    before = {k:raw.get(k) for k in (*fiscal.PUBLIC_FIELDS,'v2_series','v2_invoice_series','enabled_in_v2')}
    changes = payload.model_dump(exclude_unset=True)
    if db.query(FiscalJob.id).first() and any(changes.get(k,raw.get(k)) != raw.get(k) for k in ('ruc','environment')):
        raise HTTPException(409,'Ya existen comprobantes V2: no se puede cambiar RUC o entorno.')
    for key,prefix in (('v2_series','B'),('v2_invoice_series','F')):
        if changes.get(key,raw.get(key))!=raw.get(key) and db.query(FiscalJob.id).filter(FiscalJob.series.startswith(prefix)).first():
            raise HTTPException(409,'La serie ya tiene comprobantes V2 y no se puede cambiar.')
    for key,value in changes.items():
        if key in {'sol_user','sol_password','certificate_password'} and not value:
            continue
        raw['enabled_in_v2' if key == 'enabled' else key] = value
    if raw.get('enabled_in_v2') and raw.get('test_batch'):
        raise HTTPException(409,'Desactiva primero el modo de pruebas; no se permite enviar a SUNAT durante las pruebas.')
    try:
        if raw.get('enabled_in_v2'):
            fiscal.validate_configuration(db,raw)
    except FiscalError as exc:
        raise HTTPException(422,str(exc)) from exc
    fiscal.persist_config(row,raw)
    audit_change(db,request,user,'medical_billing_configuration',row.id,before=before,
                 after={**{k:raw.get(k) for k in before},'credentials_updated':any(changes.get(k) for k in ('sol_user','sol_password','certificate_password'))},module='abissol_medical')
    db.commit()
    return fiscal.public_configuration(db)


@router.post('/billing/{ident}/retry')
def retry_invoice(ident: int, request: Request, db: Session = Depends(get_db), user=Depends(require_access('medical-billing','gestor'))):
    if not fiscal.programmer(user):
        raise HTTPException(403,'Solo Programador puede revisar la cola fiscal')
    job = db.query(FiscalJob).filter_by(invoice_id=ident).with_for_update().first()
    if not job or job.state in {'accepted','rejected'}:
        raise HTTPException(409,'No existe una operación pendiente que se pueda revisar.')
    before = job.state
    job.state = 'uncertain' if job.sent_at else 'queued'
    from ..utils.time import utc_now
    job.next_attempt_at = utc_now()
    audit_change(db,request,user,'medical_fiscal_jobs',job.id,before={'state':before},after={'state':job.state},module='abissol_medical')
    db.commit()
    return {'state':job.state}


@router.get('/billing/{ident}/detail')
def invoice_detail(ident: int, db: Session = Depends(get_db), user=Depends(require_access('medical-billing'))):
    row = find(invoice_scope(db, user), ident)
    logs = (row.details or {}).get('sunat_logs', [])
    if row.legacy_id:
        for record in db.query(LegacyRecord).filter_by(source_table='billing_sunat_logs'):
            raw = json.loads(decrypt_secret(record.payload_encrypted))
            if raw.get('invoice_id') == row.legacy_id:
                logs.append({key: raw.get(key) for key in ('action', 'status', 'created_at', 'error_type', 'error_category', 'severity')})
    return {**dump(row), 'details': row.details or {}, 'sunat_logs': logs}


@router.get('/billing/{ident}/files/{kind}')
def invoice_file(ident: int, kind: str, db: Session = Depends(get_db), user=Depends(require_access('medical-billing'))):
    row = find(invoice_scope(db, user), ident)
    if not row.legacy_id and (row.details or {}).get('files', {}).get(kind):
        try:
            path = fiscal.artifact_path(row,kind)
        except FiscalError as exc:
            raise HTTPException(404,str(exc)) from exc
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.details['files'][kind]:
            raise HTTPException(409,'Archivo fiscal ausente o integridad no válida.')
        return FileResponse(path,filename=f'{row.full_number}-{kind}{path.suffix}',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    file_id = (row.details or {}).get('files', {}).get(kind)
    if not file_id:
        raise HTTPException(404, 'Archivo no disponible')
    return legacy_download(db, file_id=file_id)


@router.post("/billing")
def create_invoice(payload: InvoiceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-billing", "editor"))):
    if fiscal.configuration(db)[1].get('enabled_in_v2'):
        raise HTTPException(409,'La boleta se genera automáticamente al registrar la emisión.')
    emission = find(scope(db, user).filter(Issuance.status == "issued"), payload.issuance_id, True)
    if db.query(Invoice.id).filter_by(issuance_id=emission.id).first():
        raise HTTPException(409, 'La emisión ya tiene comprobantes; revisa su historial fiscal')
    return save(db, request, user, Invoice(**payload.model_dump(), draft_key=emission.id, total=emission.price, created_by=user.id))


@router.put("/billing/{ident}")
def update_invoice(ident: int, payload: InvoiceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-billing", "editor"))):
    row = find(db.query(Invoice).filter(Invoice.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery())), ident, True)
    if row.legacy_id or row.status != "draft" or row.issuance_id != payload.issuance_id:
        raise HTTPException(409, "Solo se pueden corregir los datos del borrador original")
    before = dump(row)
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    return save(db, request, user, row, before)


@router.get("/dispatches")
def dispatches(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user=Depends(require_access("medical-dispatches"))):
    query = db.query(Dispatch)
    if not admin(user):
        query = query.filter(or_(Dispatch.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery()), Dispatch.liquidation_id.in_(liquidation_scope(db, user).with_entities(Liquidation.id).scalar_subquery())))
    total = query.count()
    rows = query.add_columns(Issuance.code, Liquidation.code, Invoice.full_number).outerjoin(Issuance, Issuance.id == Dispatch.issuance_id).outerjoin(Liquidation, Liquidation.id == Dispatch.liquidation_id).outerjoin(Invoice, Invoice.id == Dispatch.invoice_id).order_by(Dispatch.id.desc()).offset(offset).limit(limit).all()
    return {"items": [{**dump(row), "issuance_code": code, "liquidation_code": liquidation_code, "invoice_number": invoice_number} for row, code, liquidation_code, invoice_number in rows], "total": total}


def deliver(db, request, user, row, emission, real_test=False):
    from ..services.medical_testing import check_delivery
    check_delivery(db, emission, row.channel, row.recipient, real_test)
    before = dump(row)
    row.attempts += 1
    row.status, row.error = "sending", ""
    # Persistir el intento antes de contactar al proveedor; un corte no genera reintento automático.
    save(db, request, user, row, before)
    url = public_url(request, emission)
    if emission.test_batch and not real_test:
        row.status='simulated'
        row.error='PRUEBA: envío registrado sin contactar correo ni WhatsApp.'
        return save(db,request,user,row,{'status':'sending'})
    from ..services.medical_settings import insured_message
    try:
        if row.channel == "email":
            from ..services.medical_information import letter_file,conditions_file,welcome_message
            archived=letter_file(db,emission)
            attachment=archived[0].read_bytes() if archived else letter_pdf(emission,url)
            attachments=[('carta-bienvenida-abissol.pdf',attachment,'application/pdf')]
            conditioned=conditions_file(db,emission)
            if conditioned:attachments.append((conditioned[1],conditioned[0].read_bytes(),conditioned[2]))
            body,html_body=welcome_message(db,emission,url,condition_available=bool(conditioned))
            if emission.test_batch:
                body='PRUEBA — NO ACREDITA COBERTURA REAL\n\n'+body
                html_body='<p><strong>PRUEBA — NO ACREDITA COBERTURA REAL</strong></p>'+html_body
            send_email(db,row.recipient,('PRUEBA · ' if emission.test_batch else '')+f'Bienvenido a ABISSOL · {emission.plan_name}',body,html=html_body,attachments=attachments)

        else:
            body = insured_message(db, emission, row.channel, url)
            if emission.test_batch:body='PRUEBA — NO ACREDITA COBERTURA REAL\n\n'+body
            send_whatsapp(db, row.recipient, body)
        row.status = "sent"
    except Exception:
        row.status, row.error = "failed", "El proveedor no confirmó el envío. Revisa la configuración y su registro antes de reintentar."
    return save(db, request, user, row, {**dump(row), "status": "sending"})


@router.post("/dispatches")
def create_dispatch(payload: DispatchInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-dispatches", "editor"))):
    emission = find(scope(db, user).filter(Issuance.status == "issued"), payload.issuance_id)
    recipient = emission.email if payload.channel == "email" else emission.phone
    if not recipient:
        raise HTTPException(422, "La emisión no tiene un destinatario registrado para este canal")
    row = Dispatch(**payload.model_dump(), recipient=recipient, created_by=user.id, attempts=0)
    return deliver(db, request, user, row, emission)


@router.post("/dispatches/{ident}/retry")
def retry_dispatch(ident: int, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-dispatches", "editor"))):
    row = find(db.query(Dispatch).filter(Dispatch.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery())), ident, True)
    if row.kind in {"meta_daily_report", "metafin_monthly", "invoice_client"}:
        raise HTTPException(409, "Los reportes META se reenvían desde su pestaña con confirmación explícita")
    if row.legacy_id:
        raise HTTPException(409, 'Comunicación histórica: no se reenvía desde la migración')
    emission = find(scope(db, user).filter(Issuance.status == "issued"), row.issuance_id)
    if row.status != "failed":
        raise HTTPException(409, "Solo se reintentan envíos fallidos; un envío en curso requiere comprobar el proveedor")
    return deliver(db, request, user, row, emission)


@router.get("/reports")
def reports(starts_on: date | None = None, ends_on: date | None = None, db: Session = Depends(get_db), user=Depends(require_access("medical-reports"))):
    query = filtered(scope(db, user), "", starts_on, ends_on).filter(Issuance.test_batch.is_(None), Issuance.status == "issued")
    totals = query.with_entities(func.count(Issuance.id), func.coalesce(func.sum(Issuance.price), 0),
        func.coalesce(func.sum(Issuance.paid_amount), 0), func.coalesce(func.sum(Issuance.seller_commission), 0), func.coalesce(func.sum(Issuance.provider_cost), 0)).one()
    groups = query.with_entities(Issuance.plan_name, func.count(Issuance.id), func.sum(Issuance.price)).group_by(Issuance.plan_name).all()
    return {"count": totals[0], "sales": str(totals[1]), "collected": str(totals[2]), "pending": str(totals[1] - totals[2]),
            "commissions": str(totals[3]), "provider_cost": str(totals[4]),
            "items": [{"plan": name, "count": count, "sales": str(sales)} for name, count, sales in groups], "total": len(groups)}
