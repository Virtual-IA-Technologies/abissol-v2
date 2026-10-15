"""Federated directory: names and live presence, isolated from business data."""
import asyncio
import logging
import os
from datetime import timedelta

from fastapi import Depends, HTTPException
from sqlalchemy.dialects.mysql import insert

from ..database import SessionLocal
from ..models.device_session import DeviceSession
from ..models.support_chat import SupportChatPresence
from ..models.user import Usuario
from ..utils.jwt import get_current_identity
from ..utils.time import utc_now

DIRECTORY_INTERVAL_SECONDS = 5
PRESENCE_TTL_SECONDS = 60


def chat_identity(identity=Depends(get_current_identity)):
    if identity.impersonation_id is not None:
        raise HTTPException(403, 'Vuelve a tu cuenta para usar el chat')
    if identity.effective_user.requiere_cambio_clave:
        raise HTTPException(403, 'Cambia tu contraseña antes de usar el chat')
    return identity


def chat_user(identity=Depends(chat_identity)):
    return identity.effective_user


def touch_presence(db, session_id):
    now = utc_now()
    # Upsert avoids races between tabs sharing the same device session.
    statement = insert(SupportChatPresence).values(device_session_id=session_id, seen_at=now)
    db.execute(statement.on_duplicate_key_update(seen_at=now))
    db.commit()


def directory_snapshot(db):
    now = utc_now()
    online = {user_id for (user_id,) in db.query(DeviceSession.usuario_id).join(
        SupportChatPresence, SupportChatPresence.device_session_id == DeviceSession.id
    ).filter(DeviceSession.revoked_at.is_(None), DeviceSession.expires_at > now,
             SupportChatPresence.seen_at > now - timedelta(seconds=PRESENCE_TTL_SECONDS)).distinct()}
    return [{'external_id': str(user.id), 'name': f'{user.nombre} {user.apellido or ""}'.strip(),
             'state': 'conectado' if user.id in online else 'desconectado'}
            for user in db.query(Usuario).filter(Usuario.is_active.is_(True), Usuario.deleted_at.is_(None))]


def snapshot():
    with SessionLocal() as db:
        return directory_snapshot(db)


async def directory_loop():
    from ..routes.support_chat import relay
    while True:
        if os.getenv('SUPPORT_CHAT_URL') and os.getenv('SUPPORT_CHAT_TOKEN'):
            try:
                people = await asyncio.to_thread(snapshot)
                await relay('POST', '/bridge/directory', None, json={'people': people}, timeout=5)
            except Exception:
                # Never log credentials, names, upstream bodies or request URLs.
                logging.getLogger(__name__).warning('Directorio de Sistemas no disponible; se reintentará')
        await asyncio.sleep(DIRECTORY_INTERVAL_SECONDS)
