from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.calendar import CalendarEvent, CalendarLabel, CalendarReminder
from ..models.user import Usuario
from ..schemas.calendar import CalendarEventOut, CalendarEventUpdate, CalendarEventWrite, CalendarLabelOut, CalendarLabelWrite
from ..services.access_control import require_access
from ..utils.time import utc_iso, utc_now
from .audit import audit_change

router = APIRouter()


def _query(db: Session):
    return db.query(CalendarEvent).options(
        joinedload(CalendarEvent.propietario),
        joinedload(CalendarEvent.asignados),
        joinedload(CalendarEvent.etiquetas),
        joinedload(CalendarEvent.recordatorios),
    )


def _visible(query, user: Usuario):
    return query.filter(or_(
        CalendarEvent.visibilidad == "equipo",
        CalendarEvent.propietario_id == user.id,
        CalendarEvent.asignados.any(Usuario.id == user.id),
    ))


def _person(user: Usuario) -> dict:
    return {"id": user.id, "nombre": f"{user.nombre} {user.apellido}".strip(), "username": user.username}


def _event_out(event: CalendarEvent) -> dict:
    return {
        "id": event.id,
        "titulo": event.titulo,
        "descripcion": event.descripcion,
        "inicio": utc_iso(event.inicio),
        "fin": utc_iso(event.fin),
        "todo_el_dia": bool(event.todo_el_dia),
        "estado": event.estado,
        "prioridad": event.prioridad,
        "visibilidad": event.visibilidad,
        "ubicacion": event.ubicacion,
        "propietario": _person(event.propietario),
        "asignados": sorted((_person(user) for user in event.asignados), key=lambda item: item["nombre"]),
        "etiquetas": sorted(({
            "id": label.id, "nombre": label.nombre, "color": label.color, "is_active": bool(label.is_active),
        } for label in event.etiquetas), key=lambda item: item["nombre"]),
        "recordatorios": sorted(({
            "id": reminder.id, "minutos_antes": reminder.minutos_antes, "canal": reminder.canal,
        } for reminder in event.recordatorios), key=lambda item: (item["minutos_antes"], item["canal"])),
        "origen_modulo": event.origen_modulo,
        "origen_tipo": event.origen_tipo,
        "origen_id": event.origen_id,
        "origen_url": event.origen_url,
        "version": event.version,
        "created_at": utc_iso(event.created_at),
        "updated_at": utc_iso(event.updated_at),
    }


def _event_or_404(db: Session, event_id: int, user: Usuario) -> CalendarEvent:
    event = _visible(_query(db), user).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return event


def _relations(
    db: Session,
    assigned_ids: list[int],
    label_ids: list[int],
    allowed_inactive_label_ids: set[int] | None = None,
):
    assigned = db.query(Usuario).filter(Usuario.id.in_(assigned_ids), Usuario.is_active.is_(True)).all() if assigned_ids else []
    allowed_inactive_label_ids = allowed_inactive_label_ids or set()
    labels = db.query(CalendarLabel).filter(
        CalendarLabel.id.in_(label_ids),
        or_(CalendarLabel.is_active.is_(True), CalendarLabel.id.in_(allowed_inactive_label_ids)),
    ).all() if label_ids else []
    if len(assigned) != len(assigned_ids):
        raise HTTPException(status_code=422, detail="Uno o más responsables no existen o están inactivos")
    if len(labels) != len(label_ids):
        raise HTTPException(status_code=422, detail="Una o más etiquetas no existen o están inactivas")
    return assigned, labels


@router.get("/calendario/eventos", response_model=list[CalendarEventOut])
def list_events(
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
    buscar: str = Query(default="", max_length=200),
    estado: str = Query(default="todos", pattern=r"^(todos|pendiente|confirmado|en_progreso|completado|cancelado)$"),
    asignado_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("calendario", "lector")),
):
    query = _visible(_query(db), user)
    try:
        parsed_from = None if not desde else datetime.fromisoformat(desde.replace("Z", "+00:00"))
        parsed_to = None if not hasta else datetime.fromisoformat(hasta.replace("Z", "+00:00"))
        from_dt = parsed_from.astimezone(UTC).replace(tzinfo=None) if parsed_from and parsed_from.tzinfo else parsed_from
        to_dt = parsed_to.astimezone(UTC).replace(tzinfo=None) if parsed_to and parsed_to.tzinfo else parsed_to
    except ValueError:
        raise HTTPException(status_code=422, detail="Rango de fechas inválido")
    if from_dt is not None:
        query = query.filter(CalendarEvent.fin > from_dt)
    if to_dt is not None:
        query = query.filter(CalendarEvent.inicio < to_dt)
    if estado != "todos":
        query = query.filter(CalendarEvent.estado == estado)
    if asignado_id is not None:
        query = query.filter(or_(CalendarEvent.propietario_id == asignado_id, CalendarEvent.asignados.any(Usuario.id == asignado_id)))
    term = buscar.strip().lower()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(
            func.lower(CalendarEvent.titulo).like(pattern),
            func.lower(CalendarEvent.descripcion).like(pattern),
            func.lower(CalendarEvent.ubicacion).like(pattern),
            func.lower(CalendarEvent.origen_modulo).like(pattern),
            CalendarEvent.etiquetas.any(func.lower(CalendarLabel.nombre).like(pattern)),
        ))
    rows=query.order_by(CalendarEvent.inicio, CalendarEvent.id).all()
    return [_event_out(event) for event in sorted(rows,key=lambda row:(row.inicio,row.id)) if (from_dt is None or event.fin>from_dt) and (to_dt is None or event.inicio<to_dt)]


@router.get("/calendario/eventos/{event_id}", response_model=CalendarEventOut)
def get_event(event_id: int, db: Session = Depends(get_db), user: Usuario = Depends(require_access("calendario", "lector"))):
    return _event_out(_event_or_404(db, event_id, user))


@router.post("/calendario/eventos", response_model=CalendarEventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: CalendarEventWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("calendario", "editor")),
):
    assigned, labels = _relations(db, payload.asignado_ids, payload.etiqueta_ids)
    values = payload.model_dump(exclude={"asignado_ids", "etiqueta_ids", "recordatorios"})
    event = CalendarEvent(**values, propietario_id=actor.id, asignados=assigned, etiquetas=labels)
    event.recordatorios = [CalendarReminder(**item.model_dump()) for item in payload.recordatorios]
    db.add(event)
    db.flush()
    snapshot = _event_out(event)
    audit_change(db, request, actor, "calendar_events", event.id, after=snapshot)
    db.commit()
    return _event_out(_event_or_404(db, event.id, actor))


@router.put("/calendario/eventos/{event_id}", response_model=CalendarEventOut)
def update_event(
    event_id: int,
    payload: CalendarEventUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("calendario", "editor")),
):
    event = _event_or_404(db, event_id, actor)
    if event.version != payload.version:
        raise HTTPException(status_code=409, detail="El evento cambió en otra sesión; vuelve a cargarlo")
    before = _event_out(event)
    data = payload.model_dump(exclude_unset=True)
    for required in ("titulo", "inicio", "fin", "estado", "prioridad", "visibilidad"):
        if required in data and data[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} no puede quedar vacío")
    assigned_ids = data.pop("asignado_ids", None)
    label_ids = data.pop("etiqueta_ids", None)
    reminders = data.pop("recordatorios", None)
    data.pop("version", None)
    if assigned_ids is not None or label_ids is not None:
        assigned, labels = _relations(
            db,
            assigned_ids if assigned_ids is not None else [item.id for item in event.asignados],
            label_ids if label_ids is not None else [item.id for item in event.etiquetas],
            {item.id for item in event.etiquetas},
        )
        if assigned_ids is not None:
            event.asignados = assigned
        if label_ids is not None:
            event.etiquetas = labels
    if reminders is not None:
        event.recordatorios = [CalendarReminder(**item) for item in reminders]
    for key, value in data.items():
        setattr(event, key, value)
    if event.fin <= event.inicio:
        raise HTTPException(status_code=422, detail="La fecha final debe ser posterior a la inicial")
    event.version += 1
    event.updated_at = utc_now()
    db.flush()
    audit_change(db, request, actor, "calendar_events", event.id, before=before, after=_event_out(event))
    db.commit()
    return _event_out(_event_or_404(db, event.id, actor))


@router.delete("/calendario/eventos/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("calendario", "gestor")),
):
    event = _event_or_404(db, event_id, actor)
    audit_change(db, request, actor, "calendar_events", event.id, before=_event_out(event))
    db.delete(event)
    db.commit()


@router.get("/calendario/etiquetas", response_model=list[CalendarLabelOut])
def list_labels(db: Session = Depends(get_db), _: Usuario = Depends(require_access("calendario", "lector"))):
    return db.query(CalendarLabel).filter(CalendarLabel.is_active.is_(True)).order_by(CalendarLabel.nombre).all()


@router.post("/calendario/etiquetas", response_model=CalendarLabelOut, status_code=status.HTTP_201_CREATED)
def create_label(
    payload: CalendarLabelWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("calendario", "editor")),
):
    name = payload.nombre.strip()
    existing = db.query(CalendarLabel).filter(func.lower(CalendarLabel.nombre) == name.lower()).first()
    if existing and existing.is_active:
        raise HTTPException(status_code=409, detail="La etiqueta ya existe")
    if existing:
        before = {"nombre": existing.nombre, "color": existing.color, "is_active": False}
        existing.nombre = name
        existing.color = payload.color.lower()
        existing.is_active = True
        existing.created_by = actor.id
        label = existing
        db.flush()
        audit_change(
            db,
            request,
            actor,
            "calendar_labels",
            label.id,
            before=before,
            after={"nombre": label.nombre, "color": label.color, "is_active": True},
        )
    else:
        label = CalendarLabel(nombre=name, color=payload.color.lower(), created_by=actor.id)
        db.add(label)
        db.flush()
        audit_change(db, request, actor, "calendar_labels", label.id, after={"nombre": label.nombre, "color": label.color})
    db.commit()
    db.refresh(label)
    return label


@router.delete("/calendario/etiquetas/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("calendario", "gestor")),
):
    label = db.get(CalendarLabel, label_id)
    if not label or not label.is_active:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    label.is_active = False
    audit_change(db, request, actor, "calendar_labels", label.id, before={"is_active": True}, after={"is_active": False})
    db.commit()


@router.get("/calendario/personas")
def list_people(db: Session = Depends(get_db), _: Usuario = Depends(require_access("calendario", "lector"))):
    users = db.query(Usuario).filter(Usuario.is_active.is_(True)).order_by(Usuario.nombre, Usuario.apellido).all()
    return [_person(user) for user in users]


@router.get("/calendario/notificaciones")
def list_notifications(
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("notificaciones", "lector")),
    _: Usuario = Depends(require_access("calendario", "lector")),
):
    now = utc_now()
    until = now + timedelta(days=7)
    events = _visible(_query(db), user).filter(
        CalendarEvent.inicio < until,
        CalendarEvent.estado.notin_(("completado", "cancelado")),
    ).order_by(CalendarEvent.inicio).limit(50).all()
    return [{**_event_out(event), "categoria": "vencido" if event.inicio < now else "proximo"} for event in events]


def _ics_escape(value: str | None) -> str:
    return (value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/calendario/exportar.ics")
def export_ics(db: Session = Depends(get_db), user: Usuario = Depends(require_access("calendario", "lector"))):
    events = _visible(_query(db), user).order_by(CalendarEvent.inicio).all()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ABISSOL V2//Calendario//ES", "CALSCALE:GREGORIAN"]
    for event in events:
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:abissol-{event.id}@calendar",
            f"DTSTAMP:{utc_now().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{event.inicio.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{event.fin.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{_ics_escape(event.titulo)}",
            f"DESCRIPTION:{_ics_escape(event.descripcion)}",
            f"LOCATION:{_ics_escape(event.ubicacion)}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return Response(
        content="\r\n".join(lines) + "\r\n",
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=abissol-calendario.ics"},
    )
