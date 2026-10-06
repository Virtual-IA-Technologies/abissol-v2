"""Operación comercial ABISSOL con permisos de menú y alcance por registro."""
import hashlib
import html
import io
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import pymupdf as fitz
import qrcode
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response, HTMLResponse, JSONResponse
from sqlalchemy import false, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Usuario
from ..models.medical import (MedicalPlan as Plan, MedicalSource as Source, MedicalProfile as Profile,
    MedicalIssuance as Issuance, MedicalLiquidation as Liquidation, MedicalLiquidationItem as Item,
    MedicalVoucher as Voucher, MedicalInvoice as Invoice, MedicalDispatch as Dispatch)
from ..schemas.medical import (PlanInput, SourceInput, ProfileInput, IssuanceInput, PaymentInput,
    ReasonInput, LiquidationInput, InvoiceInput, DispatchInput)
from ..services.access_control import require_access, ensure_option_access
from ..services.email import send_email
from ..services.whatsapp import send_whatsapp
from ..services.commercial_roles import seed_commercial_roles, ROLE_NAMES
from ..utils.jwt import get_current_identity
from .audit import audit_change

router = APIRouter(prefix="/medical")
STORAGE = Path(__file__).resolve().parents[2] / "storage" / "medical"


def dump(row):
    # Decimal convertido a texto para no perder precisión en auditoría/JSON.
    return {c.name: str(getattr(row, c.name)) if isinstance(getattr(row, c.name), Decimal)
            else jsonable_encoder(getattr(row, c.name)) for c in row.__table__.columns}


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
        audit_change(db, request, user, row.__tablename__, row.id, before=before, after=dump(row), module="abissol_medical")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "El código, referencia o registro ya existe; actualiza la lista") from exc
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
    people = profiles_scope(db, user).all()
    source_ids = {p.source_id for p in people}
    sources = db.query(Source)
    if not admin(user):
        sources = sources.filter(Source.id.in_(source_ids))
    users = db.query(Usuario).filter(Usuario.deleted_at.is_(None))
    if section != "network" or not admin(user):
        users = users.filter(Usuario.id.in_([p.user_id for p in people]))
    return {"plans": [dump(p) for p in db.query(Plan).order_by(Plan.name)],
            "sources": [dump(s) for s in sources.order_by(Source.name)],
            "profiles": [dump(p) for p in people],
            "users": [{"id": u.id, "name": f"{u.nombre} {u.apellido or ''}".strip(), "is_active": u.is_active, "roles": [r.nombre for r in u.active_roles()]} for u in users],
            "emissions": [{"id": e.id, "code": e.code, "customer": e.customer} for e in scope(db, user).filter(Issuance.status == "issued").order_by(Issuance.id.desc()).limit(200)] if section in {"billing", "dispatches"} else [],
            "global_access": admin(user), "fiscal_enabled": False}


@router.get("/plans")
def plans(db: Session = Depends(get_db), user=Depends(require_access("medical-plans"))):
    return {"items": [dump(p) for p in db.query(Plan).order_by(Plan.id)], "total": db.query(Plan).count()}


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
              offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user=Depends(require_access("medical-emissions"))):
    return page(filtered(scope(db, user), search, starts_on, ends_on), offset, limit)


@router.post("/emissions")
def create_emission(payload: IssuanceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions", "editor"))):
    if payload.payment_status == "paid_to_abissol" and not admin(user):
        raise HTTPException(403, "Administración debe confirmar los ingresos a ABISSOL")
    today = datetime.now(ZoneInfo("America/Lima")).date()
    if payload.starts_on <= today:
        raise HTTPException(422, "La vigencia debe comenzar desde mañana (hora de Lima)")
    emitter = find(profiles_scope(db, user).filter(Profile.active.is_(True)), payload.emitter_id)
    if emitter.user_id is None:
        raise HTTPException(422, "Este participante es externo sin acceso al portal; sus emisiones deben ingresar por su integración")
    if payload.external_source or payload.external_reference:
        raise HTTPException(422, "El portal registra emisiones directas. La identidad de integración se valida por un conector externo autenticado")
    if emitter.kind == "source_admin":
        raise HTTPException(422, "Selecciona un responsable o emisor comercial")
    find(db.query(Source).filter_by(active=True), emitter.source_id)
    responsible = find(db.query(Profile).filter_by(active=True, kind="responsible", source_id=emitter.source_id), emitter.manager_id if emitter.kind == "emitter" else emitter.id)
    plan = find(db.query(Plan).filter_by(active=True), payload.plan_id, True)
    plan.counter += 1
    values = payload.model_dump()
    values.update(code=f"{plan.prefix}-{plan.counter:06d}", token=secrets.token_urlsafe(32),
                  plan_name=plan.name, source_id=emitter.source_id, responsible_id=responsible.id,
                  sale_date=today, ends_on=payload.starts_on + timedelta(days=plan.validity_days - 1),
                  price=plan.price, provider_cost=plan.provider_cost, seller_commission=plan.seller_commission,
                  platform_fee=plan.platform_fee, meta_commission=(plan.provider_cost * plan.meta_percent / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), conditions_url=plan.conditions_url, created_by=user.id,
                  paid_amount=plan.price if payload.payment_status != "pending" else Decimal(0))
    return save(db, request, user, Issuance(**values))


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
    return str(request.base_url).rstrip("/") + "/abissol/api/v1/medical/validate/" + row.token


def letter_pdf(row, url):
    document = fitz.open()
    sheet = document.new_page()
    sheet.draw_rect(fitz.Rect(0, 0, 595, 140), color=(.12, .33, .21), fill=(.12, .33, .21))
    sheet.insert_text((45, 65), "ABISSOL", fontsize=28, color=(1, 1, 1))
    sheet.insert_text((45, 103), "Asociacion de Bienestar, Inclusion, Salud y Solidaridad", fontsize=11, color=(1, 1, 1))
    lines = ["CARTA DE BIENVENIDA", "", f"Certificado: {row.code}", f"Plan: {row.plan_name}",
             f"Titular: {row.customer}", f"Documento: {row.document_type} {row.document_number}",
             f"Vigencia: {row.starts_on} al {row.ends_on}", f"Importe: S/ {row.price}",
             f"Estado: {'Anulado' if row.status == 'cancelled' else 'Emitido'}", "",
             "Consulta la vigencia y el estado mediante el codigo QR.",
             "Los servicios se sujetan al condicionado del plan contratado."]
    sheet.insert_textbox(fitz.Rect(45, 175, 550, 550), "\n".join(lines), fontsize=12, lineheight=1.7)
    buf = io.BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    sheet.insert_image(fitz.Rect(45, 585, 195, 735), stream=buf.getvalue())
    if row.conditions_url:
        sheet.insert_text((225, 650), "Consultar condiciones del plan", fontsize=11, color=(.12, .33, .21))
        sheet.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(220, 630, 520, 665), "uri": row.conditions_url})
    result = document.tobytes()
    document.close()
    return result


@router.get("/emissions/{ident}/letter")
def letter(ident: int, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions"))):
    row = find(scope(db, user), ident)
    return Response(letter_pdf(row, public_url(request, row)), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{row.code}.pdf"', "Cache-Control": "no-store"})


@router.get("/validate/{token}")
def validate(token: str, request: Request, db: Session = Depends(get_db)):
    if len(token) != 43:
        raise HTTPException(404, "Certificado no encontrado")
    row = db.query(Issuance).filter_by(token=token).first()
    if not row:
        raise HTTPException(404, "Certificado no encontrado")
    today = datetime.now(ZoneInfo("America/Lima")).date()
    valid = row.status == "issued" and row.starts_on <= today <= row.ends_on
    if "text/html" in request.headers.get("accept", ""):
        status = "Anulado" if row.status == "cancelled" else "Vigente" if valid else "Vigencia por iniciar" if today < row.starts_on else "Vencido"
        return HTMLResponse(f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Verificación ABISSOL</title><style>body{{margin:0;background:#102b20;color:#18362a;font:16px system-ui;display:grid;place-items:center;min-height:100vh}}main{{background:#fff;border-radius:24px;padding:32px;margin:16px;max-width:440px}}h1{{color:#287343}}dt{{color:#526b60;margin-top:18px}}dd{{margin:4px 0;font-weight:600}}small{{display:block;margin-top:24px;color:#526b60}}</style><main><h1>ABISSOL</h1><p>Verificación de certificado</p><dl><dt>Certificado</dt><dd>{html.escape(row.code)}</dd><dt>Plan</dt><dd>{html.escape(row.plan_name)}</dd><dt>Vigencia</dt><dd>{row.starts_on} al {row.ends_on}</dd><dt>Estado</dt><dd>{status}</dd></dl><small>Verificación pública sin datos personales del titular.</small></main></html>''', headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})
    return JSONResponse(jsonable_encoder({"organization": "ABISSOL", "certificate": row.code, "plan": row.plan_name,
            "starts_on": row.starts_on, "ends_on": row.ends_on, "status": row.status,
            "valid_now": valid}), headers={"Cache-Control": "no-store"})


def liquidation_scope(db, user):
    query = db.query(Liquidation)
    if admin(user):
        return query
    own = profile(db, user)
    if not own or own.kind == "emitter":
        return query.filter(false())
    return query.filter(Liquidation.kind == "seller", Liquidation.responsible_id.in_(profiles_scope(db, user).with_entities(Profile.id).scalar_subquery()))


@router.get("/liquidations")
def liquidations(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations"))):
    return page(liquidation_scope(db, user), offset, limit)


@router.post("/liquidations")
def create_liquidation(payload: LiquidationInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    own = profile(db, user)
    if not admin(user) and (not own or own.kind == "emitter" or payload.kind != "seller"):
        raise HTTPException(403, "Tu perfil no puede preparar esta liquidación")
    find(profiles_scope(db, user).filter(Profile.kind == "responsible"), payload.responsible_id)
    eligible = scope(db, user).filter(Issuance.responsible_id == payload.responsible_id, Issuance.status == "issued",
        Issuance.payment_status.in_(["collected_by_seller", "paid_to_abissol", "settled"]),
        Issuance.sale_date >= payload.starts_on, Issuance.sale_date <= payload.ends_on)
    used = db.query(Item.issuance_id).filter(Item.active_key.like(payload.kind + ":%"))
    eligible = eligible.filter(~Issuance.id.in_(used.scalar_subquery())).order_by(Issuance.id).with_for_update().all()
    if not eligible:
        raise HTTPException(422, "No hay emisiones cobradas disponibles en este período")
    row = Liquidation(**payload.model_dump(), created_by=user.id, sales_total=0, commission_total=0, deposit_required=0)
    db.add(row)
    db.flush()
    for emission in eligible:
        commission = emission.seller_commission if payload.kind == "seller" else emission.meta_commission if payload.kind == "meta" else emission.platform_fee
        deposit = emission.price if payload.kind == "seller" and emission.payment_status == "collected_by_seller" else commission if payload.kind != "seller" else Decimal(0)
        db.add(Item(liquidation_id=row.id, issuance_id=emission.id, active_key=f"{payload.kind}:{emission.id}", sale=emission.price, commission=commission, deposit=deposit))
        row.sales_total += emission.price
        row.commission_total += commission
        row.deposit_required += deposit
    return save(db, request, user, row)


@router.get("/liquidations/{ident}")
def liquidation_detail(ident: int, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations"))):
    row = find(liquidation_scope(db, user), ident)
    result = dump(row)
    result["items"] = [dump(i) for i in db.query(Item).filter_by(liquidation_id=ident)]
    result["vouchers"] = [{k: v for k, v in dump(i).items() if k not in {"storage_key", "digest", "active_digest", "active_reference"}} for i in db.query(Voucher).filter_by(liquidation_id=ident, active=True)]
    result["voucher_total"] = str(db.query(func.coalesce(func.sum(Voucher.amount), 0)).filter_by(liquidation_id=ident, active=True).scalar())
    return result


@router.post("/liquidations/{ident}/vouchers")
async def add_voucher(ident: int, request: Request, reference: str = Form(..., min_length=3, max_length=100), amount: Decimal = Form(..., gt=0, max_digits=12, decimal_places=2), paid_on: date = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    row = find(liquidation_scope(db, user), ident, True)
    if row.status not in {"draft", "observed"}:
        raise HTTPException(409, "Los comprobantes solo se cargan antes de presentar la liquidación")
    if len(reference.strip()) < 3:
        raise HTTPException(422, "La referencia debe tener al menos tres caracteres")
    if paid_on > datetime.now(ZoneInfo("America/Lima")).date():
        raise HTTPException(422, "La fecha del comprobante no puede estar en el futuro")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Máximo 5 MB por comprobante")
    suffix = ".pdf" if content.startswith(b"%PDF-") else ".png" if content.startswith(b"\x89PNG\r\n\x1a\n") else ".jpg" if content.startswith(b"\xff\xd8\xff") else None
    if not suffix:
        raise HTTPException(422, "Adjunta un PDF o imagen PNG/JPEG")
    STORAGE.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(24) + suffix
    target = STORAGE / key
    target.write_bytes(content)
    try:
        digest = hashlib.sha256(content).hexdigest()
        result = save(db, request, user, Voucher(liquidation_id=ident, reference=reference.strip(), active_reference=reference.strip().upper(), amount=amount, paid_on=paid_on,
            filename=Path(file.filename or "comprobante").name[:180], storage_key=key, digest=digest, active_digest=digest))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {k: v for k, v in result.items() if k not in {"storage_key", "digest", "active_digest", "active_reference"}}


@router.post("/vouchers/{ident}/void")
def void_voucher(ident: int, payload: ReasonInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    row = find(db.query(Voucher).filter_by(active=True), ident)
    liquidation = find(liquidation_scope(db, user), row.liquidation_id, True)
    if liquidation.status not in {"draft", "observed"}:
        raise HTTPException(409, "El comprobante ya forma parte de una conciliación presentada")
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
    before = dump(row)
    transitions = {"submit": ({"draft", "observed"}, "submitted"), "approve": ({"submitted"}, "approved"),
                   "observe": ({"submitted"}, "observed"), "pay": ({"approved"}, "paid"), "cancel": ({"draft", "observed"}, "cancelled")}
    if action not in transitions or row.status not in transitions[action][0]:
        raise HTTPException(409, "La acción no corresponde al estado actual")
    if action in {"approve", "observe", "pay"}:
        ensure_option_access(db, user, "medical-liquidations", "gestor")
        global_only(user)
    if action in {"submit", "approve", "pay"}:
        total = db.query(func.coalesce(func.sum(Voucher.amount), 0)).filter_by(liquidation_id=ident, active=True).scalar()
        if total != row.deposit_required:
            raise HTTPException(422, f"Los comprobantes suman {total}; se requiere {row.deposit_required}")
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
    return page(db.query(Invoice).filter(Invoice.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery())), offset, limit)


@router.post("/billing")
def create_invoice(payload: InvoiceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-billing", "editor"))):
    emission = find(scope(db, user).filter(Issuance.status == "issued"), payload.issuance_id, True)
    return save(db, request, user, Invoice(**payload.model_dump(), total=emission.price, created_by=user.id))


@router.put("/billing/{ident}")
def update_invoice(ident: int, payload: InvoiceInput, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-billing", "editor"))):
    row = find(db.query(Invoice).filter(Invoice.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery())), ident, True)
    if row.status != "draft" or row.issuance_id != payload.issuance_id:
        raise HTTPException(409, "Solo se pueden corregir los datos del borrador original")
    before = dump(row)
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    return save(db, request, user, row, before)


@router.get("/dispatches")
def dispatches(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user=Depends(require_access("medical-dispatches"))):
    return page(db.query(Dispatch).filter(Dispatch.issuance_id.in_(scope(db, user).with_entities(Issuance.id).scalar_subquery())), offset, limit)


def deliver(db, request, user, row, emission):
    before = dump(row)
    row.attempts += 1
    row.status, row.error = "sending", ""
    # Persistir el intento antes de contactar al proveedor; un corte no genera reintento automático.
    save(db, request, user, row, before)
    url = public_url(request, emission)
    body = f"ABISSOL: {emission.plan_name}. Certificado {emission.code}. Vigencia {emission.starts_on} al {emission.ends_on}. Verificación: {url}"
    try:
        if row.channel == "email":
            send_email(db, row.recipient, f"ABISSOL · {emission.code}", body, attachments=[(emission.code + ".pdf", letter_pdf(emission, url), "application/pdf")])
        else:
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
    emission = find(scope(db, user).filter(Issuance.status == "issued"), row.issuance_id)
    if row.status != "failed":
        raise HTTPException(409, "Solo se reintentan envíos fallidos; un envío en curso requiere comprobar el proveedor")
    return deliver(db, request, user, row, emission)


@router.get("/reports")
def reports(starts_on: date | None = None, ends_on: date | None = None, db: Session = Depends(get_db), user=Depends(require_access("medical-reports"))):
    query = filtered(scope(db, user), "", starts_on, ends_on).filter(Issuance.status == "issued")
    totals = query.with_entities(func.count(Issuance.id), func.coalesce(func.sum(Issuance.price), 0),
        func.coalesce(func.sum(Issuance.paid_amount), 0), func.coalesce(func.sum(Issuance.seller_commission), 0), func.coalesce(func.sum(Issuance.provider_cost), 0)).one()
    groups = query.with_entities(Issuance.plan_name, func.count(Issuance.id), func.sum(Issuance.price)).group_by(Issuance.plan_name).all()
    return {"count": totals[0], "sales": str(totals[1]), "collected": str(totals[2]), "pending": str(totals[1] - totals[2]),
            "commissions": str(totals[3]), "provider_cost": str(totals[4]),
            "items": [{"plan": name, "count": count, "sales": str(sales)} for name, count, sales in groups], "total": len(groups)}
