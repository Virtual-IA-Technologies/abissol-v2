from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..utils.time import utc_now

from ..database import get_db
from ..models.rol import Rol
from ..models.user import Usuario, UsuarioRol
from ..models.wolverine import AccessGrant, Menu
from ..utils.jwt import AuthIdentity, get_current_identity

ACCESS_RANK = {"none": 0, "lector": 1, "editor": 2, "gestor": 3}


def ensure_option_access(db: Session, user: Usuario, menu_slug: str, minimum: str = "lector") -> Menu:
    if minimum not in ACCESS_RANK:
        raise ValueError(f"Nivel de acceso ABISSOL inválido: {minimum}")
    if user.requiere_cambio_clave:
        raise HTTPException(status_code=403, detail="Debes cambiar tu contraseña antes de continuar")
    menu = db.query(Menu).filter(Menu.slug == menu_slug, Menu.is_active.is_(True)).first()
    if not menu:
        raise HTTPException(status_code=403, detail="La opción no está habilitada")
    level = effective_access(db, user, [menu]).get(menu.id, ("none", ""))[0]
    if ACCESS_RANK[level] < ACCESS_RANK[minimum]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso insuficiente")
    return menu


def _valid_now(query, now: datetime):
    return query.filter(
        AccessGrant.is_active.is_(True),
        or_(AccessGrant.starts_at.is_(None), AccessGrant.starts_at <= now),
        or_(AccessGrant.ends_at.is_(None), AccessGrant.ends_at >= now),
    )


def effective_access(
    db: Session,
    user: Usuario,
    menus: list[Menu] | None = None,
) -> dict[int, tuple[str, str]]:
    active_roles = user.active_roles()
    menu_ids = [menu.id for menu in menus] if menus is not None else [
        menu_id for (menu_id,) in db.query(Menu.id).filter(Menu.is_active.is_(True)).all()
    ]
    if any(role.es_superusuario for role in active_roles):
        return {menu_id: ("gestor", "superuser") for menu_id in menu_ids}

    now = utc_now()
    role_ids = [role.id for role in active_roles]
    result: dict[int, tuple[str, str]] = {}
    if role_ids:
        grants = _valid_now(db.query(AccessGrant), now).filter(
            AccessGrant.role_id.in_(role_ids),
            AccessGrant.menu_id.in_(menu_ids),
        ).all()
        for grant in grants:
            current = result.get(grant.menu_id)
            if current is None or ACCESS_RANK[grant.access_level] > ACCESS_RANK[current[0]]:
                result[grant.menu_id] = (grant.access_level, "role")

    # Una asignación individual siempre prevalece sobre los roles.
    individual = _valid_now(db.query(AccessGrant), now).filter(
        AccessGrant.usuario_id == user.id,
        AccessGrant.menu_id.in_(menu_ids),
    ).all()
    for grant in individual:
        result[grant.menu_id] = (grant.access_level, "user")
    return result


def access_by_slug(
    db: Session,
    user: Usuario,
    resolved: dict[int, tuple[str, str]] | None = None,
    menus: list[Menu] | None = None,
) -> dict[str, str]:
    resolved = resolved if resolved is not None else effective_access(db, user, menus)
    rows = [(menu.id, menu.slug) for menu in menus] if menus is not None else db.query(
        Menu.id, Menu.slug
    ).filter(Menu.is_active.is_(True)).all()
    return {
        slug: resolved[menu_id][0]
        for menu_id, slug in rows
        if menu_id in resolved and resolved[menu_id][0] != "none"
    }


def menu_tree(
    rows: list[Menu],
    resolved: dict[int, tuple[str, str]] | None = None,
    *,
    effective_only: bool = False,
) -> list[dict]:
    resolved = resolved or {}
    by_parent: dict[int | None, list[Menu]] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)

    def build(parent_id: int | None) -> list[dict]:
        result = []
        for menu in sorted(by_parent.get(parent_id, []), key=lambda item: (item.orden, item.id)):
            children = build(menu.id)
            level, source = resolved.get(menu.id, ("none", None))
            if effective_only and ACCESS_RANK[level] < ACCESS_RANK["lector"] and not children:
                continue
            result.append({
                "id": menu.id,
                "parent_id": menu.parent_id,
                "nombre": menu.nombre,
                "slug": menu.slug,
                "ruta": menu.ruta,
                "icono": menu.icono,
                "tipo": menu.tipo,
                "orden": menu.orden,
                "is_visible": bool(menu.is_visible),
                "is_active": bool(menu.is_active),
                "access_level": level if level != "none" else None,
                "access_source": source,
                "children": children,
            })
        return result

    return build(None)


def effective_menu_tree(
    db: Session,
    user: Usuario,
    *,
    include_hidden: bool = False,
    resolved: dict[int, tuple[str, str]] | None = None,
    menus: list[Menu] | None = None,
) -> list[dict]:
    rows = menus if menus is not None else db.query(Menu).filter(Menu.is_active.is_(True)).all()
    resolved = resolved if resolved is not None else effective_access(db, user, rows)
    visible_rows = rows if include_hidden else [menu for menu in rows if menu.is_visible]
    return menu_tree(visible_rows, resolved, effective_only=True)


def require_access(menu_slug: str, minimum: str = "lector"):
    if minimum not in ACCESS_RANK:
        raise ValueError(f"Nivel de acceso ABISSOL inválido: {minimum}")

    def dependency(
        identity: AuthIdentity = Depends(get_current_identity),
        db: Session = Depends(get_db),
    ) -> Usuario:
        ensure_option_access(db, identity.effective_user, menu_slug, minimum)
        return identity.effective_user

    return dependency


def user_with_roles(db: Session, user_id: int) -> Usuario | None:
    return db.query(Usuario).options(
        joinedload(Usuario.roles), joinedload(Usuario.role_assignments).joinedload(UsuarioRol.rol),
    ).filter(Usuario.id == user_id, Usuario.deleted_at.is_(None)).first()
