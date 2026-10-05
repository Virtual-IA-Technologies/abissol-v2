from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from ..services.notification_inbox import inbox, remove
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models.device_session import DeviceSession
from ..models.notification import Notification, NotificationPreference
from ..models.user import Usuario
from ..models.wolverine import ImpersonationSession, Menu
from ..schemas.notification import NotificationPreferencesWrite, NotificationRulesWrite
from ..services import notification_configuration
from ..services.access_control import ACCESS_RANK, effective_access, require_access, user_with_roles
from ..services.notifications import EVENT_TYPES, notification_out, socket_manager
from ..utils.jwt import verificar_token
from ..utils.time import utc_now

router = APIRouter()


@router.get('/notificaciones/reglas')
def rules(db: Session = Depends(get_db), user: Usuario = Depends(require_access('notificaciones','lector'))):
    return notification_configuration.read(db,user,EVENT_TYPES)


@router.put('/notificaciones/reglas')
def save_rules(payload: NotificationRulesWrite, request: Request, db: Session = Depends(get_db), user: Usuario = Depends(require_access('notificaciones','lector'))):
    return notification_configuration.save(db,user,payload,EVENT_TYPES,request)


def _require_programmer(user: Usuario) -> None:
    if not any(role.es_superusuario for role in user.active_roles()):
        raise HTTPException(status_code=403, detail="Solo Programador puede configurar notificaciones")


@router.get("/notificaciones")
def list_notifications(
    unread_only: bool = False,
    limit: int = 100,
    page: int = Query(1, ge=1),
    search: str = Query('', max_length=180),
    source: str = Query('', max_length=80),
    severity: str = Query('', max_length=20),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("notificaciones", "lector")),
):
    return inbox(db, user.id, unread_only=unread_only, page=page, limit=limit, search=search, source=source, severity=severity)


class InboxRemoval(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


@router.post('/notificaciones/eliminar')
def remove_notifications(payload: InboxRemoval, db: Session = Depends(get_db), user: Usuario = Depends(require_access('notificaciones', 'lector'))):
    return remove(db, user.id, payload.ids)


@router.delete('/notificaciones/{notification_id}', status_code=204)
def remove_notification(notification_id: int, db: Session = Depends(get_db), user: Usuario = Depends(require_access('notificaciones', 'lector'))):
    remove(db, user.id, [notification_id])


@router.get("/notificaciones/tipos")
def notification_types(
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("notificaciones", "lector")),
):
    _require_programmer(user)
    preferences = {
        row.event_type: bool(row.internal_enabled)
        for row in db.query(NotificationPreference).filter(NotificationPreference.usuario_id == user.id).all()
    }
    return [
        {"event_type": key, **definition, "enabled": preferences.get(key, True)}
        for key, definition in EVENT_TYPES.items()
    ]


@router.put("/notificaciones/preferencias")
def update_preferences(
    payload: NotificationPreferencesWrite,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("notificaciones", "lector")),
):
    _require_programmer(user)
    unknown = set(payload.enabled_types) - set(EVENT_TYPES)
    if unknown:
        raise HTTPException(status_code=422, detail="Existe un tipo de notificacion no reconocido")
    existing = {row.event_type: row for row in db.query(NotificationPreference).filter(NotificationPreference.usuario_id == user.id).all()}
    for event_type in EVENT_TYPES:
        preference = existing.get(event_type)
        if preference:
            preference.internal_enabled = event_type in payload.enabled_types
        else:
            db.add(NotificationPreference(usuario_id=user.id, event_type=event_type, internal_enabled=event_type in payload.enabled_types))
    db.commit()
    return {"enabled_types": payload.enabled_types}


@router.patch("/notificaciones/{notification_id}/leer")
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("notificaciones", "lector")),
):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.usuario_id == user.id, Notification.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notificacion no encontrada")
    item.read_at = item.read_at or utc_now()
    db.commit()
    return {"ok": True}


@router.post("/notificaciones/leer-todas")
def read_all_notifications(
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("notificaciones", "lector")),
):
    db.query(Notification).filter(Notification.usuario_id == user.id, Notification.deleted_at.is_(None), Notification.read_at.is_(None)).update({Notification.read_at: utc_now()}, synchronize_session=False)
    db.commit()
    return {"ok": True}


SocketUser = tuple[Session, Usuario]


def _socket_user(token: str) -> SocketUser | None:
    payload = verificar_token(token)
    if not payload:
        return None
    db = SessionLocal()
    try:
        effective_id = int(payload["sub"])
        session_id = int(payload["sid"])
        user = user_with_roles(db, effective_id)
        actor_id = int(payload.get("act", effective_id))
        actor = user if actor_id == effective_id else user_with_roles(db, actor_id)
        if not user or not actor or not user.is_active or not actor.is_active or user.requiere_cambio_clave:
            db.close()
            return None
        active = db.query(DeviceSession.id).filter(DeviceSession.id == session_id, DeviceSession.usuario_id == actor_id, DeviceSession.revoked_at.is_(None), DeviceSession.expires_at > utc_now()).first()
        impersonation_id = int(payload["imp"]) if payload.get("imp") is not None else None
        if impersonation_id is not None:
            impersonation = db.query(ImpersonationSession.id).filter(
                ImpersonationSession.id == impersonation_id,
                ImpersonationSession.impersonator_id == actor_id,
                ImpersonationSession.impersonated_id == effective_id,
                ImpersonationSession.device_session_id == session_id,
                ImpersonationSession.ended_at.is_(None),
            ).first()
            if not impersonation or not any(role.es_superusuario for role in actor.active_roles()):
                db.close()
                return None
        elif actor_id != effective_id:
            db.close()
            return None
        menu = db.query(Menu).filter(Menu.slug == "notificaciones", Menu.is_active.is_(True)).first()
        if not active or not menu or ACCESS_RANK[effective_access(db, user, [menu]).get(menu.id, ("none", ""))[0]] < ACCESS_RANK["lector"]:
            db.close()
            return None
        return db, user
    except (KeyError, TypeError, ValueError):
        db.close()
        return None


@router.websocket("/notificaciones/ws")
async def notification_socket(websocket: WebSocket):
    await websocket.accept()
    authenticated: SocketUser | None = None
    try:
        message = await websocket.receive_json()
        authenticated = _socket_user(str(message.get("token", "")))
        if not authenticated:
            await websocket.close(code=4401)
            return
        db, user = authenticated
        await socket_manager.connect(user.id, websocket)
        await websocket.send_json({"type": "ready"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if authenticated:
            db, user = authenticated
            socket_manager.disconnect(user.id, websocket)
            db.close()
