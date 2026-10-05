from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.rol import Rol
from ..models.user import Usuario
from ..schemas.roles import RoleOut, RoleUpdate, RoleWrite
from ..services.access_control import require_access

from .audit import audit_change

router = APIRouter()


def _role_out(role: Rol) -> RoleOut:
    return RoleOut(
        id=role.id,
        nombre=role.nombre,
        prioridad=role.prioridad,
        es_superusuario=bool(role.es_superusuario),
        is_active=bool(role.is_active),
        is_default=bool(role.is_default),
        user_ids=[user.id for user in role.usuarios],
    )


def _can_manage_superuser(actor: Usuario) -> bool:
    return any(role.es_superusuario for role in actor.active_roles())


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("roles", "lector")),
):
    roles = db.query(Rol).options(joinedload(Rol.usuarios).load_only(Usuario.id)).order_by(Rol.prioridad, Rol.nombre).all()
    return [_role_out(role) for role in roles]


@router.get("/roles/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("roles", "lector")),
):
    role = db.query(Rol).options(joinedload(Rol.usuarios).load_only(Usuario.id)).filter(Rol.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    return _role_out(role)


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleWrite,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("roles", "editor")),
    request: Request = None,
):
    if payload.es_superusuario and not _can_manage_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede crear roles superiores")
    if db.query(Rol.id).filter(func.lower(Rol.nombre) == payload.nombre.lower()).first():
        raise HTTPException(status_code=409, detail="El rol ya existe")
    role = Rol(**payload.model_dump())
    db.add(role)
    db.flush()
    audit_change(db, request, actor, "roles", role.id, after=_role_out(role).model_dump())
    db.commit()
    db.refresh(role)
    return _role_out(role)


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("roles", "editor")),
    request: Request = None,
):
    role = db.query(Rol).options(joinedload(Rol.usuarios)).filter(Rol.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if (role.es_superusuario or payload.es_superusuario) and not _can_manage_superuser(actor):
        raise HTTPException(status_code=403, detail="Solo Programador puede modificar roles superiores")
    before = _role_out(role).model_dump()
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    try:
        db.flush()
        audit_change(db, request, actor, "roles", role.id, before=before, after=_role_out(role).model_dump())
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El nombre del rol ya existe")
    db.refresh(role)
    return _role_out(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("roles", "gestor")),
    request: Request = None,
):
    role = db.query(Rol).options(joinedload(Rol.usuarios)).filter(Rol.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if role.es_superusuario:
        raise HTTPException(status_code=409, detail="El rol Programador no se puede eliminar")
    if role.usuarios:
        raise HTTPException(status_code=409, detail="Desasigna los usuarios antes de eliminar el rol")
    audit_change(db, request, actor, "roles", role.id, before=_role_out(role).model_dump())
    db.delete(role)
    db.commit()
