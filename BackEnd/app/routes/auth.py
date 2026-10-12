from datetime import datetime, timedelta
import html
import hashlib
import logging
import os
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..config import get_settings
from ..utils.time import utc_now

from ..database import get_db
from ..models.device_session import DeviceSession
from ..models.password_reset import PasswordResetToken
from ..models.rol import Rol
from ..models.user import Usuario, UsuarioRol
from ..models.wolverine import ImpersonationSession, LoginAttempt, Menu
from ..schemas.user import CambiarClaveObligatoria, UsuarioOut
from ..schemas.wolverine import ImpersonationOut, WolverineSession
from ..services.access_control import access_by_slug, effective_access, effective_menu_tree
from ..services.email import EmailNotConfigured, get_smtp_setting, send_email
from ..utils.jwt import AuthIdentity, crear_token, get_current_identity
from ..utils.identifiers import normalize_phone

router = APIRouter()
logger = logging.getLogger(__name__)
DEVICE_SESSION_COOKIE = "abissol_device_session"
DEVICE_SESSION_DAYS = get_settings().device_session_days
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
_DUMMY_HASH = bcrypt.hashpw(b"invalid-password", bcrypt.gensalt()).decode("utf-8")


class LoginRequest(BaseModel):
    identificador: str | None = None
    correo: str | None = None
    contrasena: str
    rememberMe: bool = True

    @model_validator(mode="after")
    def require_identifier(self):
        if not (self.identificador or self.correo or "").strip():
            raise ValueError("Ingresa tu correo, usuario o teléfono")
        return self

    @property
    def login_identifier(self) -> str:
        return (self.identificador or self.correo or "").strip()


class PasswordResetRequest(BaseModel):
    correo: EmailStr


class PasswordResetComplete(BaseModel):
    token: str
    nueva_clave: str
    confirmar_clave: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> None:
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="La contraseña no puede superar 72 bytes UTF-8")
    if len(password) < 10 or not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=422,
            detail="La contraseña debe tener al menos 10 caracteres, mayúscula, minúscula y número",
        )


def _session_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _password_reset_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _identifier_hash(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return (forwarded or (request.client.host if request.client else ""))[:64] or None


def _secure_cookie(request: Request) -> bool:
    configured = os.getenv("DEVICE_SESSION_COOKIE_SECURE")
    if configured is not None and configured.strip():
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return proto == "https" or request.url.scheme == "https"


def _set_session_cookie(response: Response, request: Request, raw_token: str, persistent: bool) -> None:
    response.set_cookie(
        key=DEVICE_SESSION_COOKIE,
        value=raw_token,
        max_age=DEVICE_SESSION_DAYS * 86400 if persistent else None,
        httponly=True,
        secure=_secure_cookie(request),
        samesite="lax",
        path="/",
    )


def _load_user(db: Session, user_id: int) -> Usuario | None:
    return db.query(Usuario).options(
        joinedload(Usuario.roles),
        joinedload(Usuario.role_assignments).joinedload(UsuarioRol.rol),
    ).filter(
        Usuario.id == user_id,
        Usuario.is_active.is_(True),
    ).first()


def _impersonation_payload(actor: Usuario, effective: Usuario, session_id: int | None) -> ImpersonationOut:
    return ImpersonationOut(
        active=session_id is not None,
        session_id=session_id,
        actor=UsuarioOut.model_validate(actor),
        effective_user=UsuarioOut.model_validate(effective),
    )


def _session_response(
    db: Session,
    actor: Usuario,
    effective: Usuario,
    device_session_id: int,
    impersonation_id: int | None = None,
) -> WolverineSession:
    menus = db.query(Menu).filter(Menu.is_active.is_(True)).all()
    resolved = effective_access(db, effective, menus)
    return WolverineSession(
        access_token=crear_token(
            effective.id,
            device_session_id,
            actor_user_id=actor.id if actor.id != effective.id else None,
            impersonation_id=impersonation_id,
        ),
        usuario=UsuarioOut.model_validate(effective),
        requiere_cambio_clave=bool(effective.requiere_cambio_clave),
        access=access_by_slug(db, effective, resolved, menus),
        menus=effective_menu_tree(db, effective, resolved=resolved, menus=menus),
        impersonation=_impersonation_payload(actor, effective, impersonation_id),
    )


def revoke_user_sessions(db: Session, usuario_id: int, reason: str = "revoked") -> None:
    now = utc_now()
    db.query(DeviceSession).filter(
        DeviceSession.usuario_id == usuario_id,
        DeviceSession.revoked_at.is_(None),
    ).update({DeviceSession.revoked_at: now, DeviceSession.revoked_reason: reason}, synchronize_session=False)
    db.query(ImpersonationSession).filter(
        ImpersonationSession.ended_at.is_(None),
        (ImpersonationSession.impersonator_id == usuario_id) | (ImpersonationSession.impersonated_id == usuario_id),
    ).update({ImpersonationSession.ended_at: now}, synchronize_session=False)


def _register_failure(db: Session, identifier: str, request: Request) -> None:
    now = utc_now()
    key = _identifier_hash(identifier)
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier_hash == key).first()
    if not attempt:
        attempt = LoginAttempt(identifier_hash=key, attempts=0)
        db.add(attempt)
    attempt.attempts += 1
    attempt.last_attempt_at = now
    attempt.ip_address = _client_ip(request)
    if attempt.attempts >= MAX_LOGIN_ATTEMPTS:
        attempt.lock_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
    db.commit()


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    try:
        get_smtp_setting(db)
    except EmailNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    generic = {"message": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña"}
    email = str(payload.correo).strip().lower()
    user = db.query(Usuario).filter(Usuario.correo == email, Usuario.is_active.is_(True)).first()
    if not user:
        return generic

    now = utc_now()
    recent = db.query(PasswordResetToken.id).filter(
        PasswordResetToken.usuario_id == user.id,
        PasswordResetToken.created_at >= now - timedelta(seconds=60),
    ).first()
    if recent:
        return generic

    db.query(PasswordResetToken).filter(
        PasswordResetToken.usuario_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(48)
    db.add(PasswordResetToken(
        usuario_id=user.id,
        token_hash=_password_reset_hash(raw_token),
        created_at=now,
        expires_at=now + timedelta(minutes=get_settings().password_reset_minutes),
        requested_ip=_client_ip(request),
    ))
    reset_url = f"{get_settings().frontend_url}/restablecer-clave?token={raw_token}"
    safe_name = html.escape(user.nombre)
    safe_url = html.escape(reset_url, quote=True)
    try:
        send_email(
            db,
            user.correo,
            "Restablece tu contraseña de ABISSOL",
            f"Hola {user.nombre},\n\nAbre este enlace para crear una nueva contraseña:\n{reset_url}\n\n"
            f"Vence en {get_settings().password_reset_minutes} minutos y solo puede usarse una vez.",
            f"<h2>Restablece tu contraseña</h2><p>Hola {safe_name},</p>"
            f"<p><a href=\"{safe_url}\">Crear nueva contraseña</a></p>"
            f"<p>El enlace vence en {get_settings().password_reset_minutes} minutos y solo puede usarse una vez.</p>",
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("No se pudo enviar el correo de recuperación de contraseña")
    return generic


@router.post("/password-reset/complete")
def complete_password_reset(payload: PasswordResetComplete, db: Session = Depends(get_db)):
    if payload.nueva_clave != payload.confirmar_clave:
        raise HTTPException(status_code=422, detail="Las contraseñas no coinciden")
    validate_password(payload.nueva_clave)
    now = utc_now()
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == _password_reset_hash(payload.token),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    ).with_for_update().first()
    if not reset:
        raise HTTPException(status_code=422, detail="El enlace es inválido, ya fue usado o venció")
    user = db.query(Usuario).filter(Usuario.id == reset.usuario_id, Usuario.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=422, detail="El enlace es inválido, ya fue usado o venció")
    if verify_password(payload.nueva_clave, user.contrasena):
        raise HTTPException(status_code=422, detail="La nueva contraseña debe ser diferente")
    user.contrasena = hash_password(payload.nueva_clave)
    user.requiere_cambio_clave = False
    db.query(PasswordResetToken).filter(
        PasswordResetToken.usuario_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    revoke_user_sessions(db, user.id, reason="password_reset_link")
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}


@router.post("/login", response_model=WolverineSession)
def login(payload: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    identifier = payload.login_identifier.lower()
    key = _identifier_hash(identifier)
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier_hash == key).first()
    now = utc_now()
    if attempt and attempt.lock_until and attempt.lock_until > now:
        raise HTTPException(status_code=423, detail="Acceso bloqueado temporalmente")
    if attempt and attempt.lock_until and attempt.lock_until <= now:
        attempt.attempts = 0
        attempt.lock_until = None

    phone = None
    try:
        phone = normalize_phone(identifier)
    except HTTPException:
        pass
    matches = [Usuario.correo == identifier, Usuario.username == identifier]
    if phone:
        matches.append(Usuario.telefono == phone)
    user = db.query(Usuario).options(
        joinedload(Usuario.roles),
        joinedload(Usuario.role_assignments).joinedload(UsuarioRol.rol),
    ).filter(
        or_(*matches),
        Usuario.is_active.is_(True),
    ).first()
    valid = verify_password(payload.contrasena, user.contrasena if user else _DUMMY_HASH)
    if not user or not valid:
        _register_failure(db, identifier, request)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    if attempt:
        db.delete(attempt)

    raw_token = secrets.token_urlsafe(48)
    device_session = DeviceSession(
        usuario_id=user.id,
        token_hash=_session_hash(raw_token),
        persistent=payload.rememberMe,
        user_agent=request.headers.get("user-agent", "")[:255] or None,
        ip_address=_client_ip(request),
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=DEVICE_SESSION_DAYS),
    )
    db.add(device_session)
    # El flush asigna el ID sin expirar al usuario ni sus roles. Construir la
    # respuesta antes del commit evita recargar ambos objetos en el mismo login.
    db.flush()
    session_payload = _session_response(db, user, user, device_session.id)
    audit_identity = AuthIdentity(user, user, device_session.id)
    db.commit()
    request.state.auth_identity = audit_identity
    _set_session_cookie(response, request, raw_token, payload.rememberMe)
    return session_payload


@router.post("/refresh-session", response_model=WolverineSession)
def refresh_session(response: Response, request: Request, db: Session = Depends(get_db)):
    raw_token = request.cookies.get(DEVICE_SESSION_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail="No hay sesión guardada en este equipo")
    now = utc_now()
    device_session = db.query(DeviceSession).filter(
        DeviceSession.token_hash == _session_hash(raw_token),
        DeviceSession.revoked_at.is_(None),
        DeviceSession.expires_at > now,
    ).with_for_update().first()
    if not device_session:
        response.delete_cookie(DEVICE_SESSION_COOKIE, path="/")
        raise HTTPException(status_code=401, detail="La sesión venció o fue revocada")
    actor = _load_user(db, device_session.usuario_id)
    if not actor:
        device_session.revoked_at = now
        device_session.revoked_reason = "inactive_user"
        db.commit()
        raise HTTPException(status_code=401, detail="El usuario ya no está activo")

    impersonation = db.query(ImpersonationSession).filter(
        ImpersonationSession.device_session_id == device_session.id,
        ImpersonationSession.ended_at.is_(None),
    ).order_by(ImpersonationSession.id.desc()).first()
    if impersonation and not any(role.es_superusuario for role in actor.active_roles()):
        impersonation.ended_at = now
        impersonation = None
    effective = _load_user(db, impersonation.impersonated_id) if impersonation else actor
    if not effective:
        if impersonation:
            impersonation.ended_at = now
        effective = actor
        impersonation = None

    # Rotar la credencial persistente evita reutilizar una cookie robada anteriormente.
    next_raw_token = secrets.token_urlsafe(48)
    device_session.token_hash = _session_hash(next_raw_token)
    device_session.last_used_at = now
    device_session.expires_at = now + timedelta(days=DEVICE_SESSION_DAYS)
    db.commit()
    request.state.auth_identity = AuthIdentity(actor, effective, device_session.id, impersonation.id if impersonation else None)
    _set_session_cookie(response, request, next_raw_token, bool(device_session.persistent))
    return _session_response(db, actor, effective, device_session.id, impersonation.id if impersonation else None)


@router.post("/logout-session", status_code=status.HTTP_204_NO_CONTENT)
def logout_session(response: Response, request: Request, db: Session = Depends(get_db)):
    raw_token = request.cookies.get(DEVICE_SESSION_COOKIE)
    if raw_token:
        session = db.query(DeviceSession).filter(DeviceSession.token_hash == _session_hash(raw_token)).first()
        if session and session.revoked_at is None:
            session.revoked_at = utc_now()
            session.revoked_reason = "logout"
            db.query(ImpersonationSession).filter(
                ImpersonationSession.device_session_id == session.id,
                ImpersonationSession.ended_at.is_(None),
            ).update({ImpersonationSession.ended_at: utc_now()}, synchronize_session=False)
            db.commit()
    response.delete_cookie(DEVICE_SESSION_COOKIE, path="/", secure=_secure_cookie(request), httponly=True, samesite="lax")


@router.get("/me", response_model=WolverineSession)
def me(identity: AuthIdentity = Depends(get_current_identity), db: Session = Depends(get_db)):
    return _session_response(db, identity.actor_user, identity.effective_user, identity.device_session_id, identity.impersonation_id)


@router.post("/cambiar-clave-obligatoria")
def change_required_password(
    payload: CambiarClaveObligatoria,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    if identity.impersonation_id:
        raise HTTPException(status_code=409, detail="No se puede cambiar una clave durante la impersonación")
    if payload.nueva_clave != payload.confirmar_clave:
        raise HTTPException(status_code=422, detail="Las contraseñas no coinciden")
    validate_password(payload.nueva_clave)
    user = db.get(Usuario, identity.effective_user.id)
    if verify_password(payload.nueva_clave, user.contrasena):
        raise HTTPException(status_code=422, detail="La nueva contrasena debe ser diferente")
    user.contrasena = hash_password(payload.nueva_clave)
    user.requiere_cambio_clave = False
    revoke_user_sessions(db, user.id, reason="password_changed")
    db.commit()
    return {"message": "Contraseña actualizada; vuelve a iniciar sesión", "requiere_cambio_clave": False}


@router.post("/impersonation/start/{user_id}", response_model=WolverineSession)
def start_impersonation(
    user_id: int,
    request: Request,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    if identity.impersonation_id or identity.actor_user.id != identity.effective_user.id:
        raise HTTPException(status_code=409, detail="Finaliza la impersonación actual")
    if not any(role.es_superusuario for role in identity.actor_user.active_roles()):
        raise HTTPException(status_code=403, detail="Solo Programador puede impersonar usuarios")
    if identity.actor_user.requiere_cambio_clave:
        raise HTTPException(403, "Debes cambiar tu contraseña antes de continuar")
    target = _load_user(db, user_id)
    if not target or target.id == identity.actor_user.id:
        raise HTTPException(status_code=422, detail="Usuario de destino inválido")
    if any(role.es_superusuario for role in target.active_roles()):
        raise HTTPException(status_code=403, detail="No se puede impersonar otro Programador")
    if target.requiere_cambio_clave:
        raise HTTPException(409, "El usuario debe completar su cambio de contraseña antes de impersonarlo")
    session = ImpersonationSession(
        impersonator_id=identity.actor_user.id,
        impersonated_id=target.id,
        device_session_id=identity.device_session_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:255] or None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    request.state.auth_identity = AuthIdentity(identity.actor_user, target, identity.device_session_id, session.id)
    return _session_response(db, identity.actor_user, target, identity.device_session_id, session.id)


@router.post("/impersonation/leave", response_model=WolverineSession)
def leave_impersonation(
    request: Request,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    if not identity.impersonation_id:
        raise HTTPException(status_code=409, detail="No existe una impersonación activa")
    session = db.get(ImpersonationSession, identity.impersonation_id)
    session.ended_at = utc_now()
    db.commit()
    request.state.auth_identity = AuthIdentity(identity.actor_user, identity.actor_user, identity.device_session_id)
    return _session_response(db, identity.actor_user, identity.actor_user, identity.device_session_id)
