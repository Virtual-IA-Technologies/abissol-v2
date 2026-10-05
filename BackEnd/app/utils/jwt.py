from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from ..config import get_settings
from ..utils.time import utc_now

from ..database import get_db
from ..models.device_session import DeviceSession
from ..models.user import Usuario, UsuarioRol
from ..models.wolverine import ImpersonationSession

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthIdentity:
    actor_user: Usuario
    effective_user: Usuario
    device_session_id: int
    impersonation_id: int | None = None
    actor_user_id: int = field(init=False)
    effective_user_id: int = field(init=False)

    def __post_init__(self) -> None:
        # La auditoría se ejecuta después de responder; conservar escalares evita
        # reconsultar modelos que SQLAlchemy haya expirado tras un commit.
        object.__setattr__(self, "actor_user_id", self.actor_user.id)
        object.__setattr__(self, "effective_user_id", self.effective_user.id)


def crear_token(
    user_id: int,
    device_session_id: int,
    *,
    actor_user_id: int | None = None,
    impersonation_id: int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    now = utc_now()
    payload = {
        "sub": str(user_id),
        "sid": device_session_id,
        "iat": now,
        "exp": now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
    }
    if actor_user_id is not None:
        payload["act"] = str(actor_user_id)
    if impersonation_id is not None:
        payload["imp"] = impersonation_id
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def _load_user(db: Session, user_id: int) -> Usuario | None:
    return (
        db.query(Usuario)
        .options(
            joinedload(Usuario.roles),
            joinedload(Usuario.role_assignments).joinedload(UsuarioRol.rol),
        )
        .filter(Usuario.id == user_id, Usuario.is_active.is_(True))
        .first()
    )


def get_current_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> AuthIdentity:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verificar_token(credentials.credentials) if credentials else None
    if not payload:
        raise unauthorized
    try:
        effective_id = int(payload["sub"])
        actor_id = int(payload.get("act", effective_id))
        session_id = int(payload["sid"])
        impersonation_id = int(payload["imp"]) if payload.get("imp") is not None else None
    except (KeyError, TypeError, ValueError):
        raise unauthorized

    actor = _load_user(db, actor_id)
    effective = actor if effective_id == actor_id else _load_user(db, effective_id)
    if not actor or not effective:
        raise unauthorized
    active_session = db.query(DeviceSession.id).filter(
        DeviceSession.id == session_id,
        DeviceSession.usuario_id == actor.id,
        DeviceSession.revoked_at.is_(None),
        DeviceSession.expires_at > utc_now(),
    ).first()
    if not active_session:
        raise unauthorized

    if impersonation_id is not None:
        if not any(role.es_superusuario for role in actor.active_roles()):
            raise unauthorized
        active = db.query(ImpersonationSession.id).filter(
            ImpersonationSession.id == impersonation_id,
            ImpersonationSession.impersonator_id == actor.id,
            ImpersonationSession.impersonated_id == effective.id,
            ImpersonationSession.device_session_id == session_id,
            ImpersonationSession.ended_at.is_(None),
        ).first()
        if not active:
            raise unauthorized
    elif actor.id != effective.id:
        raise unauthorized

    identity = AuthIdentity(actor, effective, session_id, impersonation_id)
    request.state.auth_identity = identity
    return identity


def get_current_user(identity: AuthIdentity = Depends(get_current_identity)) -> Usuario:
    return identity.effective_user
