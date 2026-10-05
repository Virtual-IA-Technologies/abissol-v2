import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from sqlalchemy import event
from sqlalchemy.orm import Session, selectinload

from ..models.notification import Notification, NotificationPreference, NotificationRule
from ..models.calendar import CalendarEvent
from .notification_rules import may_receive, recipient_matches
from ..models.user import Usuario, UsuarioRol
from ..models.wolverine import Menu
from ..services.access_control import ACCESS_RANK, effective_access


EVENT_TYPES = {
    "usuarios.crear": {"source": "Usuarios", "label": "Usuario creado", "severity": "info"},
    "usuarios.modificar": {"source": "Usuarios", "label": "Usuario modificado", "severity": "info"},
    "usuarios.eliminar": {"source": "Usuarios", "label": "Usuario eliminado", "severity": "warning"},
    "roles.crear": {"source": "Roles", "label": "Rol creado", "severity": "info"},
    "roles.modificar": {"source": "Roles", "label": "Rol modificado", "severity": "info"},
    "roles.eliminar": {"source": "Roles", "label": "Rol eliminado", "severity": "warning"},
    "calendar_events.crear": {"source": "Calendario", "label": "Evento creado", "severity": "info"},
    "calendar_events.modificar": {"source": "Calendario", "label": "Evento modificado", "severity": "info"},
    "calendar_events.eliminar": {"source": "Calendario", "label": "Evento eliminado", "severity": "warning"},
}


class NotificationSocketManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: int, websocket: WebSocket):
        self.loop = asyncio.get_running_loop()
        self.connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        self.connections[user_id].discard(websocket)
        if not self.connections[user_id]:
            self.connections.pop(user_id, None)

    async def broadcast(self, payloads: list[dict[str, Any]]):
        for payload in payloads:
            for websocket in list(self.connections.get(payload["usuario_id"], set())):
                try:
                    await websocket.send_json({"type": "notification", "notification": payload})
                except Exception:
                    self.disconnect(payload["usuario_id"], websocket)

    def broadcast_after_commit(self, payloads: list[dict[str, Any]]):
        if self.loop and self.loop.is_running() and payloads:
            asyncio.run_coroutine_threadsafe(self.broadcast(payloads), self.loop)


socket_manager = NotificationSocketManager()


@event.listens_for(Session, "after_commit")
def _publish_committed(session: Session):
    socket_manager.broadcast_after_commit(session.info.pop("notification_payloads", []))


@event.listens_for(Session, "after_rollback")
def _discard_rolled_back(session: Session):
    session.info.pop("notification_payloads", None)


def _url(entity: str, entity_id: str | int) -> str | None:
    if entity == "usuarios":
        return f"/plataforma/administracion/usuarios?buscar={entity_id}"
    if entity == "roles":
        return "/plataforma/administracion/roles"
    if entity == "calendar_events":
        return f"/plataforma/sistema/calendario?evento={entity_id}"
    return None


def publish_audit_notification(
    db: Session,
    action: str,
    entity: str,
    entity_id: str | int,
    detail: str,
    *,
    dedupe_key: str | None = None,
    actor_id: int | None = None,
):
    event_type = f"{entity}.{action}"
    definition = EVENT_TYPES.get(event_type)
    if not definition:
        return
    source_slug={'usuarios':'usuarios','roles':'roles','calendar_events':'calendario'}.get(entity)
    menus=db.query(Menu).filter(Menu.slug.in_(['notificaciones',source_slug]),Menu.is_active.is_(True)).all()
    menu=next((m for m in menus if m.slug=='notificaciones'),None)
    source_menu=next((m for m in menus if m.slug==source_slug),None)
    if not menu or not source_menu:
        return
    disabled_user_ids = {
        row.usuario_id
        for row in db.query(NotificationPreference).filter(
            NotificationPreference.event_type == event_type,
            NotificationPreference.internal_enabled.is_(False),
        ).all()
    }
    rule=db.get(NotificationRule,event_type)
    recipients=rule.recipients if rule else {'kind':'eligible'}
    participants=set()
    if entity=='calendar_events':
        source=db.get(CalendarEvent,int(entity_id))
        if source:participants={source.propietario_id,*[person.id for person in source.asignados]}
    candidates=db.query(Usuario).options(selectinload(Usuario.roles),selectinload(Usuario.role_assignments).joinedload(UsuarioRol.rol)).filter(Usuario.is_active.is_(True),Usuario.deleted_at.is_(None)).all()
    for user in candidates:
        user_id=user.id
        if user_id in disabled_user_ids or user_id == actor_id:
            continue
        if not recipient_matches(user,recipients,participants):
            continue
        access=effective_access(db,user,menus)
        if any(ACCESS_RANK[access.get(m.id,('none',''))[0]]<ACCESS_RANK['lector'] for m in menus):
            continue
        if not may_receive(db,user,entity,entity_id,menus=menus,access=access):
            continue
        if dedupe_key and db.query(Notification.id).filter(
            Notification.usuario_id == user.id,
            Notification.dedupe_key == dedupe_key,
        ).first():
            continue
        notification = Notification(
            usuario_id=user.id,
            event_type=event_type,
            source=definition["source"],
            severity=definition["severity"],
            title=definition["label"],
            message=detail,
            entity=entity,
            entity_id=str(entity_id),
            url=_url(entity, entity_id),
            dedupe_key=dedupe_key,
        )
        db.add(notification)
        db.flush()
        db.info.setdefault("notification_payloads", []).append(notification_out(notification))


def notification_out(item: Notification) -> dict[str, Any]:
    return {
        "id": item.id,
        "usuario_id": item.usuario_id,
        "event_type": item.event_type,
        "source": item.source,
        "severity": item.severity,
        "title": item.title,
        "message": item.message,
        "entity": item.entity,
        "entity_id": item.entity_id,
        "url": item.url,
        "read_at": item.read_at.isoformat() + "Z" if item.read_at else None,
        "created_at": item.created_at.isoformat() + "Z",
    }
