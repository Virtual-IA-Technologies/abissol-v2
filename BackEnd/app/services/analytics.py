from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Callable
from time import monotonic
from threading import RLock
from weakref import WeakKeyDictionary
from copy import deepcopy

from sqlalchemy import and_, case, func, or_, text
from sqlalchemy.orm import Session

from ..models.audit import AuditLog
from ..models.calendar import CalendarEvent
from ..models.notification import Notification
from ..models.rol import Rol
from ..models.user import Usuario
from ..services.access_control import ACCESS_RANK, access_by_slug
from ..utils.time import utc_iso, utc_now

LIMA = timezone(timedelta(hours=-5), name="America/Lima")


def _has(access: dict[str, str], slug: str, minimum: str = "lector") -> bool:
    return ACCESS_RANK.get(access.get(slug, "none"), 0) >= ACCESS_RANK[minimum]


def _card(key: str, label: str, value: int, description: str, icon: str, tone: str, url: str) -> dict:
    return {
        "key": key, "label": label, "value": int(value), "description": description,
        "format": "integer", "icon": icon, "tone": tone, "url": url,
    }


def _money_card(key: str, label: str, value, description: str, icon: str, tone: str, url: str) -> dict:
    card = _card(key, label, 0, description, icon, tone, url)
    card.update(value=round(float(value or 0), 2), format="currency")
    return card


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _month_context(count: int = 6) -> tuple[list[date], datetime, datetime]:
    today_lima = utc_now().replace(tzinfo=UTC).astimezone(LIMA).date()
    current = today_lima.replace(day=1)
    months = [_shift_month(current, offset) for offset in range(1 - count, 1)]
    start = datetime.combine(months[0], time.min, tzinfo=LIMA).astimezone(UTC).replace(tzinfo=None)
    end = datetime.combine(_shift_month(current, 1), time.min, tzinfo=LIMA).astimezone(UTC).replace(tzinfo=None)
    return months, start, end






def _calendar_visible(query, user: Usuario):
    return query.filter(or_(
        CalendarEvent.visibilidad == "equipo",
        CalendarEvent.propietario_id == user.id,
        CalendarEvent.asignados.any(Usuario.id == user.id),
    ))


def _users_provider(db: Session, _user: Usuario) -> tuple[list[dict], list[dict]]:
    rows = dict(db.query(Usuario.is_active, func.count(Usuario.id)).group_by(Usuario.is_active).all())
    active = rows.get(True, 0)
    return [_card("users.active", "Usuarios activos", active, "Cuentas habilitadas actualmente", "users", "indigo", "/plataforma/administracion/usuarios")], [{
        "key":"users.status", "title":"Estado de cuentas", "description":"Cuentas habilitadas y deshabilitadas actualmente", "type":"donut",
        "points":[{"label":"Activas","value":active},{"label":"Inactivas","value":rows.get(False,0)}], "url":"/plataforma/administracion/usuarios",
    }]


def _roles_provider(db: Session, _user: Usuario) -> tuple[list[dict], list[dict]]:
    active = db.query(func.count(Rol.id)).filter(Rol.is_active.is_(True)).scalar() or 0
    return [_card("roles.active", "Roles activos", active, "Perfiles de acceso disponibles", "shield", "blue", "/plataforma/administracion/roles")], []


def _notifications_provider(db: Session, user: Usuario) -> tuple[list[dict], list[dict]]:
    unread = db.query(func.count(Notification.id)).filter(
        Notification.usuario_id == user.id, Notification.read_at.is_(None),
    ).scalar() or 0
    return [_card("notifications.unread", "Notificaciones pendientes", unread, "Avisos internos sin leer", "bell", "amber", "/plataforma/sistema/notificaciones")], []


def _calendar_provider(db: Session, user: Usuario) -> tuple[list[dict], list[dict]]:
    now = utc_now()
    active_states = ("pendiente", "confirmado", "en_progreso")
    rows = _calendar_visible(
        db.query(
            CalendarEvent.estado,
            func.count(CalendarEvent.id),
            func.coalesce(func.sum(case((and_(
                CalendarEvent.inicio >= now,
                CalendarEvent.inicio < now + timedelta(days=7),
                CalendarEvent.estado.in_(active_states),
            ), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                CalendarEvent.inicio < now,
                CalendarEvent.estado.in_(active_states),
            ), 1), else_=0)), 0),
        ), user,
    ).group_by(CalendarEvent.estado).all()
    upcoming = sum(int(row[2]) for row in rows)
    overdue = sum(int(row[3]) for row in rows)
    labels = {
        "pendiente": "Pendientes", "confirmado": "Confirmados", "en_progreso": "En progreso",
        "completado": "Completados", "cancelado": "Cancelados",
    }
    points = [{"label": labels.get(row[0], row[0]), "value": int(row[1])} for row in rows]
    return [
        _card("calendar.upcoming", "Próximos 7 días", upcoming, "Eventos visibles aún abiertos", "calendar", "cyan", "/plataforma/sistema/calendario"),
        _card("calendar.overdue", "Eventos vencidos", overdue, "Eventos visibles que requieren atención", "clock", "red", "/plataforma/sistema/calendario"),
    ], [{
        "key": "calendar.by_status", "title": "Calendario por estado",
        "description": "Distribución actual de los eventos que puedes consultar", "type": "donut",
        "points": points, "url": "/plataforma/sistema/calendario",
    }]


def _lima_period(days: int) -> tuple[datetime, date, datetime]:
    now_utc = utc_now()
    today_lima = now_utc.replace(tzinfo=UTC).astimezone(LIMA).date()
    first_lima = today_lima - timedelta(days=days - 1)
    start_utc = datetime.combine(first_lima, time.min, tzinfo=LIMA).astimezone(UTC).replace(tzinfo=None)
    return start_utc, first_lima, now_utc


def _audit_daily_points(db: Session, start_utc: datetime, first_lima: date, days: int) -> list[dict]:
    # Aggregate on the server: one row per day, not one row per audit event.
    local_day = (func.date(AuditLog.creado_en, "-5 hours") if db.get_bind().dialect.name == "sqlite"
                 else func.date(func.timestampadd(text("HOUR"), -5, AuditLog.creado_en)))
    rows = db.query(local_day, func.count(AuditLog.id)).filter(
        AuditLog.creado_en >= start_utc,
        AuditLog.creado_en < start_utc + timedelta(days=days),
    ).group_by(local_day).all()
    totals = {date.fromisoformat(str(day)): int(total) for day, total in rows}
    return [
        {"label": (first_lima + timedelta(days=index)).strftime("%d/%m"), "value": totals.get(first_lima + timedelta(days=index), 0)}
        for index in range(days)
    ]


def _audit_provider(db: Session, _user: Usuario) -> tuple[list[dict], list[dict]]:
    start, first_lima, _ = _lima_period(7)
    today_start, _, _ = _lima_period(1)
    base = db.query(AuditLog).filter(AuditLog.creado_en >= start)
    today_total, errors = base.with_entities(
        func.coalesce(func.sum(case((AuditLog.creado_en >= today_start, 1), else_=0)), 0),
        func.coalesce(func.sum(case((AuditLog.estado_http >= 400, 1), else_=0)), 0),
    ).one()
    modules = base.with_entities(AuditLog.modulo, func.count(AuditLog.id)).group_by(
        AuditLog.modulo,
    ).order_by(func.count(AuditLog.id).desc(), AuditLog.modulo).limit(6).all()
    return [
        _card("audit.today", "Actividad de hoy", today_total, "Movimientos registrados desde las 00:00", "activity", "emerald", "/plataforma/sistema/auditoria"),
        _card("audit.errors", "Errores en 7 días", errors, "Solicitudes auditadas con estado HTTP 4xx/5xx", "alert", "red", "/plataforma/sistema/auditoria"),
    ], [{
        "key": "audit.daily", "title": "Actividad de Auditoría",
        "description": "Movimientos reales registrados durante los últimos 7 días · hora de Lima", "type": "line",
        "points": _audit_daily_points(db, start, first_lima, 7), "url": "/plataforma/sistema/auditoria",
    }, {
        "key":"audit.modules", "title":"Actividad por módulo", "type":"bar",
        "description":"Seis módulos con más movimientos auditados en los últimos 7 días",
        "points":[{"label":module or "Sin módulo", "value":int(total)} for module,total in modules],
        "url":"/plataforma/sistema/auditoria",
    }]


def _documents_provider(db: Session, user: Usuario) -> tuple[list[dict], list[dict]]:
    from ..models.documents import Document, DocumentVersion
    from .documents import filtered, visible
    url = "/documentos/archivos?carpeta=todos&vista=all"
    current = filtered(db, user)
    total, shared, size = current.with_entities(
        func.count(Document.id),
        func.coalesce(func.sum(case((Document.owner_id != user.id, 1), else_=0)), 0),
        func.coalesce(func.sum(DocumentVersion.size), 0),
    ).one()
    group = case(
        (DocumentVersion.mime == "application/pdf", "PDF"),
        (DocumentVersion.mime.like("image/%"), "Imágenes"),
        (DocumentVersion.mime.like("text/%"), "Texto"),
        (DocumentVersion.mime.like("%wordprocessingml%"), "Word"),
        (DocumentVersion.mime.like("%spreadsheetml%"), "Excel"),
        (DocumentVersion.mime.like("%presentationml%"), "PowerPoint"), else_="Otros",
    )
    types = current.with_entities(group, func.count(Document.id)).group_by(group).order_by(func.count(Document.id).desc(), group).all()
    start, first, now = _lima_period(30)
    day = (func.date(DocumentVersion.created_at, "-5 hours") if db.get_bind().dialect.name == "sqlite"
           else func.date(func.timestampadd(text("HOUR"), -5, DocumentVersion.created_at)))
    activity = visible(db, user).filter(Document.deleted_at.is_(None)).join(DocumentVersion, DocumentVersion.document_id == Document.id)
    daily = activity.with_entities(day, func.count(DocumentVersion.id)).filter(
        DocumentVersion.created_at >= start, DocumentVersion.created_at <= now,
    ).group_by(day).all()
    totals = {str(d):int(n) for d,n in daily}
    storage = _card("documents.bytes", "Tamaño de archivos", size, "Versiones actuales visibles; excluye historial y papelera", "boxes", "cyan", url)
    storage["format"] = "bytes"
    return [
        _card("documents.visible", "Documentos disponibles", total, "Propios y compartidos contigo, sin papelera", "boxes", "blue", url),
        _card("documents.shared", "Compartidos contigo", shared, "Archivos vigentes de otros propietarios", "users", "indigo", "/documentos/archivos?carpeta=todos&vista=shared"),
        storage,
    ], [
        {"key":"documents.types", "title":"Documentos por formato", "description":"Versión actual de tus archivos accesibles, sin papelera", "type":"donut", "points":[{"label":label,"value":int(n)} for label,n in types], "url":url},
        {"key":"documents.daily", "title":"Actividad documental", "description":"Versiones creadas en 30 días de documentos actualmente accesibles · Lima", "type":"line",
         "points":[{"label":(first+timedelta(days=i)).strftime("%d/%m"),"value":totals.get(str(first+timedelta(days=i)),0)} for i in range(30)], "url":url},
    ]


Provider = Callable[[Session, Usuario], tuple[list[dict], list[dict]]]
PROVIDERS: tuple[tuple[str, Provider], ...] = (
    ("documentos", _documents_provider),
    ("notificaciones", _notifications_provider),
    ("calendario", _calendar_provider),
    ("auditoria", _audit_provider),
    ("usuarios", _users_provider),
    ("roles", _roles_provider),
)


_cache=WeakKeyDictionary()
_cache_lock=RLock()
_shared_slugs=set()


def dashboard_metrics(db: Session, user: Usuario, *, use_cache=False, refresh=False) -> dict:
    access = access_by_slug(db, user)
    cards: list[dict] = []
    charts: list[dict] = []
    generated=utc_now()
    for slug, provider in PROVIDERS:
        if _has(access, slug):
            cached=None;key=(slug,generated.replace(tzinfo=UTC).astimezone(LIMA).date())
            if use_cache and slug in _shared_slugs:
                with _cache_lock:
                    cached=_cache.get(db.get_bind(),{}).get(key)
                    if refresh or cached and monotonic()-cached[0]>=20:cached=None
            if cached:
                provider_cards,provider_charts=deepcopy(cached[2]);generated=min(generated,cached[1])
            else:
                provider_cards, provider_charts = provider(db, user)
                if use_cache and slug in _shared_slugs:
                    with _cache_lock:
                        bucket=_cache.setdefault(db.get_bind(),{})
                        if len(bucket)>24:bucket.clear()
                        bucket[key]=(monotonic(),utc_now(),deepcopy((provider_cards,provider_charts)))
            cards.extend(provider_cards)
            charts.extend(provider_charts)
    return {"generated_at": utc_iso(generated), "cards": cards, "charts": charts}


def audit_statistics(db: Session, days: int) -> dict:
    start, first_lima, now = _lima_period(days)
    base = db.query(AuditLog).filter(AuditLog.creado_en >= start)
    action = func.lower(AuditLog.accion)
    summary = base.with_entities(
        func.count(AuditLog.id),
        func.coalesce(func.sum(case((AuditLog.estado_http >= 400, 1), else_=0)), 0),
        func.count(func.distinct(AuditLog.actor_usuario_id)),
        func.count(func.distinct(AuditLog.modulo)),
        func.coalesce(func.sum(case((action.like("%crear%"), 1), else_=0)), 0),
        func.coalesce(func.sum(case((action.like("%modificar%"), 1), else_=0)), 0),
        func.coalesce(func.sum(case((action.like("%eliminar%"), 1), else_=0)), 0),
    ).one()
    total, errors, actors, modules = (int(value) for value in summary[:4])
    action_row = summary[4:]
    other = max(0, total - sum(int(value) for value in action_row))
    action_points = [
        {"label": "Creaciones", "value": int(action_row[0])},
        {"label": "Modificaciones", "value": int(action_row[1])},
        {"label": "Eliminaciones", "value": int(action_row[2])},
        {"label": "Otras", "value": other},
    ]
    top_modules = base.with_entities(AuditLog.modulo, func.count(AuditLog.id).label("total")).group_by(
        AuditLog.modulo,
    ).order_by(func.count(AuditLog.id).desc(), AuditLog.modulo).limit(8).all()
    return {
        "days": days, "from": utc_iso(start), "to": utc_iso(now),
        "cards": [
            _card("audit.period.total", "Operaciones", total, f"Movimientos de los últimos {days} días", "activity", "blue", "/plataforma/sistema/auditoria"),
            _card("audit.period.errors", "Errores HTTP", errors, "Respuestas con estado 4xx o 5xx", "alert", "red", "/plataforma/sistema/auditoria"),
            _card("audit.period.actors", "Actores", actors, "Usuarios reales con actividad", "users", "indigo", "/plataforma/sistema/auditoria"),
            _card("audit.period.modules", "Módulos", modules, "Áreas con movimientos registrados", "boxes", "cyan", "/plataforma/sistema/auditoria"),
        ],
        "charts": [
            {"key": "audit.period.daily", "title": "Actividad diaria", "description": "Operaciones por día en hora de Lima", "type": "bar", "points": _audit_daily_points(db, start, first_lima, days), "url": None},
            {"key": "audit.period.actions", "title": "Tipos de movimiento", "description": "Distribución por acción auditada", "type": "bar", "points": action_points, "url": None},
            {"key": "audit.period.modules", "title": "Módulos con más actividad", "description": "Hasta ocho módulos durante el periodo", "type": "bar", "points": [{"label": module or "Sin módulo", "value": int(total)} for module, total in top_modules], "url": None},
        ],
    }
