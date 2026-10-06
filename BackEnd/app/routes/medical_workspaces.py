"""Operational tabs from ABISSOL Laravel, with V2 permissions and audit."""
from datetime import date
from typing import Annotated, Literal
from pydantic import Field
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import medical as m
from .settings import communication_programmer
from ..database import get_db
from ..schemas.medical import Payload
from ..models.medical import MedicalBusinessSetting
from ..services.access_control import require_access
from ..services.medical_settings import BusinessSettingsInput, business_settings
from ..services.medical_exports import meta_xlsx
from ..services.email import send_email, get_smtp_setting, EmailNotConfigured
from .audit import audit_change

router = APIRouter(prefix="/medical")
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
META_KIND = "meta_daily_report"


@router.get("/emission-settings")
def get_configuration(db: Session = Depends(get_db), user=Depends(communication_programmer)):
    return {**business_settings(db), "automatic_dispatch_active": False}


@router.put("/emission-settings")
def put_configuration(payload: BusinessSettingsInput, request: Request, db: Session = Depends(get_db), user=Depends(communication_programmer)):
    before = business_settings(db)
    row = db.get(MedicalBusinessSetting, 1) or MedicalBusinessSetting(id=1)
    row.values = payload.model_dump()
    db.add(row)
    audit_change(db, request, user, "medical_business_settings", 1, before=before, after=row.values)
    db.commit()
    return {**row.values, "automatic_dispatch_active": False}


def meta_access(user):
    m.global_only(user)


def meta_query(db, user, status="pending", search="", starts_on=None, ends_on=None):
    query = m.scope(db, user).filter(m.Issuance.status == "issued")
    sent = db.query(m.Dispatch.issuance_id).filter(m.Dispatch.kind == META_KIND, m.Dispatch.status == "sent", m.Dispatch.channel == "email", m.Dispatch.issuance_id.is_not(None))
    if status == "pending":
        query = query.filter(~m.Issuance.id.in_(sent.scalar_subquery()))
    elif status != "all":
        ids = db.query(m.Dispatch.issuance_id).filter(m.Dispatch.kind == META_KIND, m.Dispatch.status == status)
        query = query.filter(m.Issuance.id.in_(ids.scalar_subquery()))
    if search:
        query = query.filter(or_(m.Issuance.code.contains(search), m.Issuance.customer.contains(search), m.Issuance.document_number.contains(search)))
    if starts_on:
        query = query.filter(m.Issuance.sale_date >= starts_on)
    if ends_on:
        query = query.filter(m.Issuance.sale_date <= ends_on)
    return query


@router.get("/meta-dispatches")
def meta_list(status: Literal["pending", "sent", "failed", "uncertain", "all"] = "pending", search: str = Query("", max_length=180), starts_on: date | None = None, ends_on: date | None = None,
              offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), db: Session = Depends(get_db), user=Depends(require_access("medical-emissions"))):
    meta_access(user)
    query = meta_query(db, user, status, search, starts_on, ends_on)
    emissions = query.order_by(m.Issuance.id.desc()).offset(offset).limit(limit).all()
    ids = [e.id for e in emissions]
    latest = {}
    for dispatch in db.query(m.Dispatch).filter(m.Dispatch.issuance_id.in_(ids), m.Dispatch.kind == META_KIND).order_by(m.Dispatch.id):
        latest[dispatch.issuance_id] = dispatch
    items = [{**m.dump(e), "dispatch_status": latest[e.id].status if e.id in latest else "pending",
              "last_dispatch_at": str(latest[e.id].created_at) if e.id in latest else None} for e in emissions]
    return {"items": items, "total": query.count(), "recipient": business_settings(db)["metafin_email"],
            "summary": {key: meta_query(db, user, key, search, starts_on, ends_on).count() for key in ("pending", "sent", "failed")}}


class MetaSelection(Payload):
    issuance_ids: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=1000)
    force: bool = False


def selected_emissions(db, user, ids, lock=False):
    query = m.scope(db, user).filter(m.Issuance.status == "issued", m.Issuance.id.in_(ids)).order_by(m.Issuance.id)
    rows = (query.with_for_update() if lock else query).all()
    if len(rows) != len(set(ids)):
        raise HTTPException(409, "La selección cambió o contiene emisiones no disponibles")
    return rows


@router.post("/meta-dispatches/export")
def meta_export(payload: MetaSelection, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions"))):
    meta_access(user)
    return Response(meta_xlsx(selected_emissions(db, user, payload.issuance_ids)), media_type=MIME,
                    headers={"Content-Disposition": 'attachment; filename="altas-meta.xlsx"', "Cache-Control": "private, no-store"})


def send_meta(db, request, user, emissions, kind, force=False, liquidation=None):
    recipient = business_settings(db)["metafin_email"]
    if not recipient:
        raise HTTPException(422, "Configura el correo META en Emisiones / Configuración")
    try:
        get_smtp_setting(db)
    except EmailNotConfigured as exc:
        raise HTTPException(422, "Configura y activa el correo SMTP antes de enviar a META") from exc
    query = db.query(m.Dispatch).filter(m.Dispatch.kind == kind)
    query = query.filter(m.Dispatch.liquidation_id == liquidation.id) if liquidation else query.filter(m.Dispatch.issuance_id.in_([e.id for e in emissions]))
    if query.filter(m.Dispatch.status == "sending").first():
        raise HTTPException(409, "Existe un envío en curso; revisa su resultado antes de repetir")
    if not force and query.filter(m.Dispatch.status.in_(["sent", "uncertain", "failed"])).first():
        raise HTTPException(409, "Hay envíos previos. Revisa el historial y confirma expresamente el reenvío")
    content = meta_xlsx(emissions)
    rows = [m.Dispatch(issuance_id=e.id, liquidation_id=liquidation.id if liquidation else None,
                       kind=kind, channel="email", recipient=recipient, status="sending", attempts=1, created_by=user.id) for e in emissions]
    db.add_all(rows)
    audit_change(db, request, user, "meta_dispatch", liquidation.id if liquidation else None,
                 after={"kind": kind, "count": len(rows), "status": "sending", "force": force})
    db.commit()  # Persist the reservation before contacting SMTP; never blindly retry.
    try:
        attachments = [("altas-meta.xlsx", content, MIME)]
        if liquidation:
            attachments.append(("carta-meta.pdf", monthly_letter(liquidation, len(emissions)), "application/pdf"))
        send_email(db, recipient, f"ABISSOL · Altas HAMPI · {liquidation.code if liquidation else 'Reporte diario'}",
                   f"Estimados META: adjuntamos {len(emissions)} altas HAMPI de ABISSOL para su registro.", attachments=attachments)
        status, error = "sent", ""
    except Exception:
        status, error = "uncertain", "SMTP no confirmó el resultado. Verifica la recepción antes de reenviar."
    for row in rows:
        row.status, row.error = status, error
    if liquidation and not liquidation.legacy_id and status == "sent" and liquidation.status in {"draft", "observed"}:
        liquidation.status = "sent"
    audit_change(db, request, user, "meta_dispatch", liquidation.id if liquidation else None, after={"kind": kind, "count": len(rows), "status": status})
    db.commit()
    return {"status": status, "count": len(rows)}


@router.post("/meta-dispatches/send")
def meta_send(payload: MetaSelection, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-emissions", "editor"))):
    meta_access(user)
    emissions = selected_emissions(db, user, payload.issuance_ids, lock=True)
    return send_meta(db, request, user, emissions, META_KIND, payload.force)


def monthly_emissions(db, user, ident, lock=False):
    row = m.find(m.liquidation_scope(db, user), ident, lock)
    if row.kind != "meta" or row.status == "cancelled":
        raise HTTPException(409, "Selecciona una liquidación mensual META activa")
    emissions = db.query(m.Issuance).join(m.Item, m.Item.issuance_id == m.Issuance.id).filter(m.Item.liquidation_id == ident).order_by(m.Issuance.id).all()
    if not emissions:
        raise HTTPException(422, "La liquidación no contiene altas")
    if any(e.status != "issued" for e in emissions):
        raise HTTPException(409, "La liquidación contiene emisiones anuladas; revisa sus altas")
    return row, emissions


def monthly_letter(row, count):
    with m.fitz.open() as document:
        page = document.new_page()
        page.insert_text((55, 65), "ABISSOL - Carta de altas HAMPI", fontsize=17)
        page.insert_textbox(m.fitz.Rect(55, 110, 540, 600),
                            f"Estimados META Assistance:\n\nAdjuntamos {count} altas del periodo {row.starts_on} al {row.ends_on}.\n\nReferencia: {row.code or row.id}\n\nEl archivo Excel contiene exclusivamente las altas incluidas en esta liquidacion.\n\nAtentamente,\nABISSOL", fontsize=12)
        return document.tobytes()


@router.get("/liquidations/{ident}/meta-file/{kind}")
def monthly_file(ident: int, kind: Literal["xlsx", "letter"], db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations"))):
    meta_access(user)
    row, emissions = monthly_emissions(db, user, ident)
    content = meta_xlsx(emissions) if kind == "xlsx" else monthly_letter(row, len(emissions))
    return Response(content, media_type=MIME if kind == "xlsx" else "application/pdf", headers={"Content-Disposition": 'attachment; filename="meta.' + ("xlsx" if kind == "xlsx" else "pdf") + '"', "Cache-Control": "private, no-store"})


class MonthlySend(Payload):
    force: bool = False


@router.post("/liquidations/{ident}/meta-send")
def monthly_send(ident: int, payload: MonthlySend, request: Request, db: Session = Depends(get_db), user=Depends(require_access("medical-liquidations", "editor"))):
    meta_access(user)
    row, emissions = monthly_emissions(db, user, ident, True)
    return send_meta(db, request, user, emissions, "metafin_monthly", payload.force, row)
