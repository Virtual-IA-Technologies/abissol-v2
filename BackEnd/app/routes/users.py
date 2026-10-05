import secrets
import string
import io
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.device_session import DeviceSession
from ..models.rol import Rol
from ..models.user import Usuario, UsuarioRol
from ..models.wolverine import AccessGrant
from ..schemas.user import (
    MiCuentaClaveUpdate, MiCuentaTemaUpdate, MiCuentaPreferenciasUpdate, MiCuentaUpdate, RoleAssignmentWrite,
    RoleMembershipWrite, UsuarioCreate, UsuarioCreateOut, UsuarioDesactivarRequest,
    UsuarioOut, UsuarioRestablecerClaveOut, UsuarioRestablecerClaveRequest, UsuarioUpdate,
)
from ..services.access_control import require_access
from ..services.user_notifications import deliver_user_credentials
from ..services.profile_assistance import authorize_profile
from ..services.upload_stream import optimized_raster
from ..utils.jwt import AuthIdentity, get_current_identity
from ..utils.identifiers import normalize_phone, normalize_username
from ..utils.time import utc_now
from .auth import hash_password, revoke_user_sessions, validate_password, verify_password

from .audit import audit_change

router = APIRouter()
AVATARS_DIR = Path(__file__).resolve().parents[2] / "storage" / "avatars"
AVATAR_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_AVATAR_BYTES = 20 * 1024 * 1024


def _reject_impersonation(identity: AuthIdentity) -> None:
    if identity.impersonation_id or identity.actor_user.id != identity.effective_user.id:
        raise HTTPException(status_code=409, detail="Finaliza la impersonación para modificar tu cuenta")


def _profile_snapshot(user: Usuario) -> dict:
    return {
        "nombre": user.nombre, "apellido": user.apellido, "username": user.username,
        "correo": user.correo, "telefono": user.telefono, "avatar_file": user.avatar_file,
    }


def _avatar_signature_matches(content: bytes, extension: str) -> bool:
    return {
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }.get(extension, False)


def _remove_avatar_file(filename: str | None) -> None:
    if not filename or Path(filename).name != filename:
        return
    path = AVATARS_DIR / filename
    if path.is_file():
        path.unlink()


def _user_query(db: Session):
    return db.query(Usuario).options(
        joinedload(Usuario.roles),
        joinedload(Usuario.role_assignments).joinedload(UsuarioRol.rol),
    ).filter(Usuario.deleted_at.is_(None))


def _is_superuser(user: Usuario) -> bool:
    return any(role.es_superusuario for role in user.active_roles())


def _ensure_manageable_user(actor: Usuario, user: Usuario) -> None:
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="No puedes cambiar el estado ni eliminar tu propia cuenta")
    if _is_superuser(user) and not _is_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede gestionar la cuenta de otro Programador")


def _roles(db: Session, role_ids: list[int], actor: Usuario) -> list[Rol]:
    roles = db.query(Rol).filter(Rol.id.in_(role_ids), Rol.is_active.is_(True)).all() if role_ids else []
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=422, detail="Uno o más roles no existen o están inactivos")
    if any(role.es_superusuario for role in roles) and not _is_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede asignar el rol superior")
    return roles


def _set_role_assignments(
    db: Session,
    user: Usuario,
    assignments: list[RoleAssignmentWrite],
    actor: Usuario,
) -> None:
    roles = _roles(db, [item.rol_id for item in assignments], actor)
    by_id = {role.id: role for role in roles}
    requested = {item.rol_id: item for item in assignments}
    existing = {item.rol_id: item for item in user.role_assignments}
    for role_id, assignment in list(existing.items()):
        if role_id not in requested:
            user.role_assignments.remove(assignment)
    for item in assignments:
        assignment = existing.get(item.rol_id)
        if assignment is None:
            assignment = UsuarioRol(rol=by_id[item.rol_id])
            user.role_assignments.append(assignment)
        assignment.is_permanent = item.is_permanent
        assignment.starts_at = item.starts_at
        assignment.ends_at = item.ends_at
        assignment.is_active = True


def _temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(14))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
            return value


def _deliver_credentials_and_audit(
    db: Session,
    request: Request | None,
    actor: Usuario,
    user: Usuario,
    temporary_password: str,
    event: str,
    *,
    email_requested: bool,
    whatsapp_requested: bool,
) -> list[dict]:
    results = deliver_user_credentials(
        db, user, temporary_password, event,
        email_requested=email_requested,
        whatsapp_requested=whatsapp_requested,
    )
    if results:
        sent = sum(1 for item in results if item["enviado"])
        audit_change(
            db, request, actor, "user_credential_notifications", f"{user.id}:{event}",
            after={"usuario_id": user.id, "evento": event, "canales": results},
            detail=f"Credenciales notificadas a {user.nombre} {user.apellido}: {sent}/{len(results)} canales enviados",
        )
        db.commit()
    return results


@router.put("/mi-cuenta", response_model=UsuarioOut)
def update_my_account(
    payload: MiCuentaUpdate,
    request: Request,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    authorize_profile(identity)
    user = _user_query(db).filter(Usuario.id == identity.effective_user.id).first()
    email = payload.correo.strip().lower()
    username = normalize_username(payload.username)
    phone = normalize_phone(payload.telefono)
    if db.query(Usuario.id).filter(Usuario.id != user.id, func.lower(Usuario.correo) == email).first():
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    if db.query(Usuario.id).filter(Usuario.id != user.id, func.lower(Usuario.username) == username).first():
        raise HTTPException(status_code=409, detail="El nombre de usuario ya está registrado")
    if phone and db.query(Usuario.id).filter(Usuario.id != user.id, Usuario.telefono == phone).first():
        raise HTTPException(status_code=409, detail="El teléfono ya está registrado")
    before = _profile_snapshot(user)
    user.nombre = payload.nombre.strip()
    user.apellido = payload.apellido.strip()
    user.username = username
    user.correo = email
    user.telefono = phone
    db.flush()
    audit_change(db, request, user, "mi_cuenta", user.id, before=before, after=_profile_snapshot(user))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El correo, usuario o teléfono ya está registrado")
    return _user_query(db).filter(Usuario.id == user.id).first()


@router.put("/mi-cuenta/clave")
def update_my_password(
    payload: MiCuentaClaveUpdate,
    request: Request,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    _reject_impersonation(identity)
    user = db.get(Usuario, identity.effective_user.id)
    if not verify_password(payload.clave_actual, user.contrasena):
        raise HTTPException(status_code=422, detail="La contraseña actual no es correcta")
    if payload.nueva_clave != payload.confirmar_clave:
        raise HTTPException(status_code=422, detail="Las contraseñas nuevas no coinciden")
    validate_password(payload.nueva_clave)
    if verify_password(payload.nueva_clave, user.contrasena):
        raise HTTPException(status_code=422, detail="La nueva contraseña debe ser diferente")
    user.contrasena = hash_password(payload.nueva_clave)
    user.requiere_cambio_clave = False
    now = utc_now()
    db.query(DeviceSession).filter(
        DeviceSession.usuario_id == user.id,
        DeviceSession.id != identity.device_session_id,
        DeviceSession.revoked_at.is_(None),
    ).update({DeviceSession.revoked_at: now, DeviceSession.revoked_reason: "password_changed"}, synchronize_session=False)
    audit_change(db, request, user, "mi_cuenta_clave", user.id, before={"clave_actualizada": False}, after={"clave_actualizada": True})
    db.commit()
    return {"message": "Contraseña actualizada; las demás sesiones fueron cerradas"}


@router.put("/mi-cuenta/tema")
def update_my_theme(
    payload: MiCuentaTemaUpdate,
    request: Request,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    authorize_profile(identity)
    user = db.get(Usuario, identity.effective_user.id)
    previous = user.tema
    user.tema = payload.tema
    audit_change(db, request, user, "mi_cuenta_tema", user.id, before={"tema": previous}, after={"tema": user.tema})
    db.commit()
    return {"tema": user.tema}


@router.put("/mi-cuenta/preferencias")
def update_my_preferences(
    payload: MiCuentaPreferenciasUpdate, request: Request,
    identity: AuthIdentity = Depends(get_current_identity), db: Session = Depends(get_db),
):
    authorize_profile(identity)
    user = db.get(Usuario, identity.effective_user.id)
    before = {"tema": user.tema, "escala": user.escala, "navigation_layout": user.navigation_layout, "menu_palette": user.menu_palette, "background_palette": user.background_palette, "menu_color": user.menu_color, "menu_tone": user.menu_tone, "background_color": user.background_color, "background_tone": user.background_tone, "appearance_overrides": user.appearance_overrides}
    user.tema, user.escala, user.navigation_layout = payload.tema, payload.escala, payload.navigation_layout
    user.menu_palette, user.background_palette = payload.menu_palette, payload.background_palette
    user.menu_color, user.menu_tone = payload.menu_color.lower(), payload.menu_tone
    user.background_color, user.background_tone = payload.background_color.lower(), payload.background_tone
    overrides = {
        theme: {**settings.model_dump(), "menu_color": settings.menu_color.lower(), "background_color": settings.background_color.lower()}
        for theme, settings in payload.appearance_overrides.items()
    }
    if not overrides:
        overrides[payload.tema] = {
            "menu_palette": payload.menu_palette, "background_palette": payload.background_palette,
            "menu_color": payload.menu_color.lower(), "menu_tone": payload.menu_tone,
            "background_color": payload.background_color.lower(), "background_tone": payload.background_tone,
        }
    user.appearance_overrides = overrides
    after = {"tema": user.tema, "escala": user.escala, "navigation_layout": user.navigation_layout, "menu_palette": user.menu_palette, "background_palette": user.background_palette, "menu_color": user.menu_color, "menu_tone": user.menu_tone, "background_color": user.background_color, "background_tone": user.background_tone, "appearance_overrides": user.appearance_overrides}
    audit_change(db, request, user, "mi_cuenta_preferencias", user.id, before=before, after=after)
    db.commit()
    return after


@router.post("/mi-cuenta/avatar", response_model=UsuarioOut)
async def upload_my_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    authorize_profile(identity)
    extension = AVATAR_TYPES.get(avatar.content_type or "")
    if extension is None:
        raise HTTPException(status_code=422, detail="El avatar debe ser PNG, JPG o WebP")
    content = await avatar.read(MAX_AVATAR_BYTES + 1)
    if not content or len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=422, detail="El avatar debe pesar como máximo 20 MB")
    if not _avatar_signature_matches(content, extension):
        raise HTTPException(status_code=422, detail="El contenido del avatar no coincide con su formato")
    try:
        normalized = await run_in_threadpool(optimized_raster, io.BytesIO(content), len(content), avatar=True)
        content = normalized.getvalue()
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    user = _user_query(db).filter(Usuario.id == identity.effective_user.id).first()
    previous = user.avatar_file
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"avatar-{user.id}-{uuid4().hex}.webp"
    (AVATARS_DIR / filename).write_bytes(content)
    user.avatar_file = filename
    audit_change(db, request, user, "mi_cuenta_avatar", user.id, before={"avatar_file": previous}, after={"avatar_file": filename})
    try:
        db.commit()
    except Exception:
        (AVATARS_DIR / filename).unlink(missing_ok=True)
        raise
    _remove_avatar_file(previous)
    return _user_query(db).filter(Usuario.id == user.id).first()


@router.delete("/mi-cuenta/avatar", response_model=UsuarioOut)
def delete_my_avatar(
    request: Request,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    authorize_profile(identity)
    user = _user_query(db).filter(Usuario.id == identity.effective_user.id).first()
    previous = user.avatar_file
    user.avatar_file = None
    audit_change(db, request, user, "mi_cuenta_avatar", user.id, before={"avatar_file": previous}, after={"avatar_file": None})
    db.commit()
    _remove_avatar_file(previous)
    return _user_query(db).filter(Usuario.id == user.id).first()


@router.get("/avatars/{filename}", name="avatar_file")
def avatar_file(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    path = AVATARS_DIR / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/usuarios", response_model=list[UsuarioOut])
def list_users(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("usuarios", "lector")),
):
    query = _user_query(db)
    if not include_inactive:
        query = query.filter(Usuario.is_active.is_(True))
    return query.order_by(Usuario.id).all()


def _assignment_snapshot(assignment: UsuarioRol | None) -> dict | None:
    if assignment is None:
        return None
    return {
        "usuario_id": assignment.usuario_id,
        "rol_id": assignment.rol_id,
        "is_permanent": bool(assignment.is_permanent),
        "starts_at": assignment.starts_at.isoformat() if assignment.starts_at else None,
        "ends_at": assignment.ends_at.isoformat() if assignment.ends_at else None,
        "is_active": bool(assignment.is_active),
    }


@router.put("/roles/{role_id}/usuarios/{user_id}", response_model=UsuarioOut)
def upsert_role_membership(
    role_id: int,
    user_id: int,
    payload: RoleMembershipWrite,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "editor")),
    request: Request = None,
):
    role = _roles(db, [role_id], actor)[0]
    user = _user_query(db).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    assignment = next((item for item in user.role_assignments if item.rol_id == role_id), None)
    before = _assignment_snapshot(assignment)
    if assignment is None:
        assignment = UsuarioRol(rol=role)
        user.role_assignments.append(assignment)
    assignment.is_permanent = payload.is_permanent
    assignment.starts_at = payload.starts_at
    assignment.ends_at = payload.ends_at
    assignment.is_active = True
    db.flush()
    audit_change(
        db, request, actor, "usuario_roles", f"{user_id}:{role_id}",
        before=before, after=_assignment_snapshot(assignment),
    )
    db.commit()
    return _user_query(db).filter(Usuario.id == user_id).first()


@router.delete("/roles/{role_id}/usuarios/{user_id}", response_model=UsuarioOut)
def delete_role_membership(
    role_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "editor")),
    request: Request = None,
):
    role = db.get(Rol, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if role.es_superusuario and not _is_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede desasignar el rol superior")
    user = _user_query(db).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    assignment = next((item for item in user.role_assignments if item.rol_id == role_id), None)
    if assignment is None:
        raise HTTPException(status_code=404, detail="El usuario no tiene asignado este rol")
    before = _assignment_snapshot(assignment)
    user.role_assignments.remove(assignment)
    db.flush()
    audit_change(db, request, actor, "usuario_roles", f"{user_id}:{role_id}", before=before)
    db.commit()
    return _user_query(db).filter(Usuario.id == user_id).first()


@router.post("/usuarios", response_model=UsuarioCreateOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "editor")),
    request: Request = None,
):
    email = payload.correo.strip().lower()
    username = normalize_username(payload.username)
    phone = normalize_phone(payload.telefono)
    if payload.notificar_whatsapp and not phone:
        raise HTTPException(status_code=422, detail="Para notificar por WhatsApp debes ingresar un telefono")
    if db.query(Usuario.id).filter(func.lower(Usuario.correo) == email).first():
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    if db.query(Usuario.id).filter(func.lower(Usuario.username) == username).first():
        raise HTTPException(status_code=409, detail="El nombre de usuario ya está registrado")
    if phone and db.query(Usuario.id).filter(Usuario.telefono == phone).first():
        raise HTTPException(status_code=409, detail="El teléfono ya está registrado")
    password = payload.contrasena or _temporary_password()
    validate_password(password)
    user = Usuario(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        username=username,
        telefono=phone,
        correo=email,
        contrasena=hash_password(password),
        requiere_cambio_clave=True,
    )
    db.add(user)
    db.flush()
    _set_role_assignments(db, user, payload.resolved_assignments() or [], actor)
    db.flush()
    db.expire(user, ["roles", "role_assignments"])
    audit_change(db, request, actor, "usuarios", user.id, after=UsuarioOut.model_validate(user).model_dump())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El correo, usuario o teléfono ya está registrado")
    db.refresh(user)
    notifications = _deliver_credentials_and_audit(
        db, request, actor, user, password, "usuarios.crear",
        email_requested=payload.notificar_correo,
        whatsapp_requested=payload.notificar_whatsapp,
    )
    return {**UsuarioOut.model_validate(user).model_dump(), "notificaciones": notifications}


@router.put("/usuarios/{user_id}", response_model=UsuarioOut)
def update_user(
    user_id: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "editor")),
    request: Request = None,
):
    user = _user_query(db).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if _is_superuser(user) and not _is_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede modificar otro Programador")
    email = payload.correo.strip().lower() if payload.correo else None
    username = user.username if payload.username == user.username else normalize_username(payload.username)
    phone = normalize_phone(payload.telefono)
    duplicate = db.query(Usuario.id).filter(
        Usuario.id != user_id,
        func.lower(Usuario.correo) == email,
    ).first()
    if email and duplicate:
        raise HTTPException(status_code=409, detail="El correo ya esta registrado")
    if db.query(Usuario.id).filter(Usuario.id != user_id, func.lower(Usuario.username) == username).first():
        raise HTTPException(status_code=409, detail="El nombre de usuario ya está registrado")
    if phone and db.query(Usuario.id).filter(Usuario.id != user_id, Usuario.telefono == phone).first():
        raise HTTPException(status_code=409, detail="El teléfono ya está registrado")
    before = UsuarioOut.model_validate(user).model_dump()
    user.nombre = payload.nombre.strip()
    user.apellido = payload.apellido.strip()
    user.username = username
    user.correo = email
    user.telefono = phone
    assignments = payload.resolved_assignments()
    if assignments is not None:
        _set_role_assignments(db, user, assignments, actor)
    if payload.contrasena:
        validate_password(payload.contrasena)
        user.contrasena = hash_password(payload.contrasena)
        user.requiere_cambio_clave = True
        revoke_user_sessions(db, user.id, reason="password_changed")
    db.flush()
    if assignments is not None:
        db.expire(user, ["roles", "role_assignments"])
    audit_change(db, request, actor, "usuarios", user.id, before=before, after=UsuarioOut.model_validate(user).model_dump())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El correo, usuario o teléfono ya está registrado")
    db.refresh(user)
    return user


@router.post("/usuarios/{user_id}/desactivar", response_model=UsuarioOut)
def deactivate_user(
    user_id: int,
    payload: UsuarioDesactivarRequest,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "gestor")),
    request: Request = None,
):
    user = _user_query(db).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _ensure_manageable_user(actor, user)
    before = UsuarioOut.model_validate(user).model_dump()
    user.is_active = False
    user.fecha_finalizacion = payload.fecha_finalizacion
    revoke_user_sessions(db, user.id, reason="user_deactivated")
    db.flush()
    audit_change(db, request, actor, "usuarios", user.id, before=before, after=UsuarioOut.model_validate(user).model_dump())
    db.commit()
    db.refresh(user)
    return user


@router.post("/usuarios/{user_id}/activar", response_model=UsuarioOut)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "gestor")),
    request: Request = None,
):
    user = _user_query(db).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _ensure_manageable_user(actor, user)
    before = UsuarioOut.model_validate(user).model_dump()
    user.is_active = True
    user.fecha_finalizacion = None
    db.flush()
    audit_change(db, request, actor, "usuarios", user.id, before=before, after=UsuarioOut.model_validate(user).model_dump())
    db.commit()
    db.refresh(user)
    return user


@router.delete("/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "gestor")),
    request: Request = None,
):
    user = _user_query(db).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _ensure_manageable_user(actor, user)
    before = UsuarioOut.model_validate(user).model_dump()
    previous_avatar = user.avatar_file
    deleted_at = utc_now()
    marker = uuid4().hex[:12]

    revoke_user_sessions(db, user.id, reason="user_deleted")
    db.query(UsuarioRol).filter(UsuarioRol.usuario_id == user.id).delete(synchronize_session=False)
    db.query(AccessGrant).filter(AccessGrant.usuario_id == user.id).delete(synchronize_session=False)
    user.nombre = "Usuario"
    user.apellido = "Eliminado"
    user.username = f"eliminado-{user.id}-{marker}"
    user.correo = f"eliminado-{user.id}-{marker}@invalid.local"
    user.telefono = None
    user.avatar_file = None
    user.contrasena = hash_password(secrets.token_urlsafe(32))
    user.is_active = False
    user.requiere_cambio_clave = False
    user.fecha_finalizacion = deleted_at.date()
    user.deleted_at = deleted_at
    db.flush()
    db.expire(user, ["roles", "role_assignments", "accesos"])
    after = UsuarioOut.model_validate(user).model_dump()
    audit_change(
        db, request, actor, "usuarios", user.id, before=before, after=after,
        action_override="eliminar",
        detail=f"Usuario eliminado: {before['nombre']} {before['apellido']} (@{before['username']})",
    )
    db.commit()
    _remove_avatar_file(previous_avatar)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/usuarios/{user_id}/restablecer-clave", response_model=UsuarioRestablecerClaveOut)
def reset_user_password(
    user_id: int,
    payload: UsuarioRestablecerClaveRequest | None = None,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("usuarios", "editor")),
    request: Request = None,
):
    user = _user_query(db).filter(Usuario.id == user_id, Usuario.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if _is_superuser(user) and not _is_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede restablecer esta cuenta")
    payload = payload or UsuarioRestablecerClaveRequest()
    if payload.notificar_whatsapp and not user.telefono:
        raise HTTPException(status_code=422, detail="El usuario necesita un telefono para recibir WhatsApp")
    before = UsuarioOut.model_validate(user).model_dump()
    temporary = _temporary_password()
    user.contrasena = hash_password(temporary)
    user.requiere_cambio_clave = True
    revoke_user_sessions(db, user.id, reason="password_reset")
    db.flush()
    audit_change(db, request, actor, "usuarios", user.id, before=before, after=UsuarioOut.model_validate(user).model_dump())
    db.commit()
    notifications = _deliver_credentials_and_audit(
        db, request, actor, user, temporary, "usuarios.restablecer_clave",
        email_requested=payload.notificar_correo,
        whatsapp_requested=payload.notificar_whatsapp,
    )
    return {
        "message": "Clave restablecida", "clave_temporal": temporary,
        "requiere_cambio_clave": True, "notificaciones": notifications,
    }
