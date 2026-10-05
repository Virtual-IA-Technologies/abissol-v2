
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..utils.time import utc_now

from ..database import get_db
from ..models.rol import Rol
from ..models.user import Usuario
from ..models.wolverine import AccessGrant, Menu
from ..schemas.wolverine import AccessGrantOut, AccessGrantWrite, MenuMove, MenuOut, MenuWrite
from ..services.access_control import effective_menu_tree, menu_tree, require_access
from ..utils.jwt import get_current_user

from .audit import audit_change

router = APIRouter()
CORE_MENU_SLUGS = {
    "plataforma", "inicio", "seccion-configuracion", "general-configuracion",
    "usuarios-seguridad", "automatizacion", "sistema", "usuarios", "roles",
    "menus", "accesos", "configuracion", "general", "apariencia", "smtp", "whatsapp",
    "plantillas", "avi-configuracion", "documentacion", "auditoria", "calendario",
    "notificaciones", "devops", "documentos", "modulo-documentos",
}
CORE_MENU_ROUTES = {
    "seccion-configuracion": "/plataforma/seccion/configuracion",
    "documentos": "/documentos/archivos",
    "usuarios": "/plataforma/administracion/usuarios",
    "roles": "/plataforma/administracion/roles",
    "accesos": "/plataforma/administracion/accesos",
    "menus": "/plataforma/sistema/menus",
    "auditoria": "/plataforma/sistema/auditoria",
    "calendario": "/plataforma/sistema/calendario",
    "notificaciones": "/plataforma/sistema/notificaciones",
    "configuracion": "/plataforma/sistema/configuracion",
    "general": "/plataforma/sistema/configuracion/general",
    "apariencia": "/plataforma/sistema/configuracion/apariencia",
    "smtp": "/plataforma/sistema/configuracion/smtp",
    "whatsapp": "/plataforma/sistema/configuracion/whatsapp",
    "plantillas": "/plataforma/sistema/configuracion/plantillas",
    "avi-configuracion": "/plataforma/automatizacion/avi",
    "documentacion": "/plataforma/sistema/documentacion",
    "devops": "/plataforma/sistema/devops",
}


def _ancestor_chain(db: Session, parent_id: int | None) -> list[Menu]:
    chain: list[Menu] = []
    visited: set[int] = set()
    while parent_id is not None:
        if parent_id in visited:
            raise HTTPException(status_code=422, detail="La jerarquia del menu contiene un ciclo")
        visited.add(parent_id)
        parent = db.get(Menu, parent_id)
        if parent is None:
            raise HTTPException(status_code=422, detail="El menu padre no existe")
        chain.append(parent)
        parent_id = parent.parent_id
    chain.reverse()
    return chain


def _menu_route(chain: list[Menu], slug: str, tipo: str) -> str | None:
    if slug in CORE_MENU_ROUTES:
        return CORE_MENU_ROUTES[slug]
    if tipo == "modulo":
        return None
    if tipo == "seccion":
        module = next((item for item in reversed(chain) if item.tipo == "modulo"), None)
        return f"/{module.slug}/seccion/{slug}" if module else None
    if not chain:
        return "/inicio" if slug == "inicio" else None
    segments = [item.slug for item in chain if item.slug != "principal"]
    return "/" + "/".join([*segments, slug])


def _validate_hierarchy(
    db: Session,
    chain: list[Menu],
    tipo: str,
    *,
    slug: str | None = None,
    moving_id: int | None = None,
) -> None:
    expected_parent = {
        "seccion": {"modulo"},
        "modulo": {"seccion"},
        "menu": {"modulo"},
        "submenu": {"menu"},
        "pestana": {"menu", "submenu"},
    }
    if tipo == "modulo" and not chain:
        return
    if tipo == "menu" and not chain and slug == "inicio":
        return
    if not chain or chain[-1].tipo not in expected_parent[tipo]:
        labels = {
            "seccion": "un modulo principal",
            "modulo": "la raiz o una seccion",
            "menu": "un modulo",
            "submenu": "un menu",
            "pestana": "un menu sin submenus o un submenu",
        }
        raise HTTPException(status_code=422, detail=f"La opcion {tipo} debe depender de {labels[tipo]}")

    for parent, child in zip(chain, chain[1:]):
        valid = child.tipo in expected_parent and parent.tipo in expected_parent[child.tipo]
        if not valid:
            raise HTTPException(status_code=422, detail="La jerarquia existente contiene niveles incompatibles")

    parent = chain[-1]
    if parent.tipo == "menu" and tipo in {"submenu", "pestana"}:
        sibling_types = {
            sibling_type
            for (sibling_type,) in db.query(Menu.tipo).filter(
                Menu.parent_id == parent.id,
                Menu.id != moving_id,
            ).all()
        }
        conflicting = "pestana" if tipo == "submenu" else "submenu"
        if conflicting in sibling_types:
            raise HTTPException(
                status_code=422,
                detail="Un menu puede contener submenus o pestanas directas, pero no ambos",
            )


def _route_for_node(menu: Menu) -> str | None:
    chain: list[Menu] = []
    parent = menu.parent
    while parent is not None:
        chain.append(parent)
        parent = parent.parent
    chain.reverse()
    return _menu_route(chain, menu.slug, menu.tipo)


def _sync_descendant_routes(menu: Menu) -> None:
    for child in menu.children:
        child.ruta = _route_for_node(child)
        _sync_descendant_routes(child)


def _resequence_siblings(db: Session, parent_id: int | None, moving_id: int, position: int) -> None:
    siblings = db.query(Menu).filter(Menu.parent_id == parent_id, Menu.id != moving_id).order_by(Menu.orden, Menu.id).all()
    moving = db.get(Menu, moving_id)
    siblings.insert(min(position, len(siblings)), moving)
    for index, sibling in enumerate(siblings, start=1):
        sibling.orden = index


@router.get("/menus", response_model=list[MenuOut])
def my_menus(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return effective_menu_tree(db, user)


@router.get("/admin/menus", response_model=list[MenuOut])
def all_menus(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("menus", "lector")),
):
    return menu_tree(db.query(Menu).all())


@router.post("/admin/menus", response_model=MenuOut, status_code=status.HTTP_201_CREATED)
def create_menu(
    payload: MenuWrite,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("menus", "editor")),
    request: Request = None,
):
    chain = _ancestor_chain(db, payload.parent_id)
    _validate_hierarchy(db, chain, payload.tipo, slug=payload.slug)
    route = _menu_route(chain, payload.slug, payload.tipo)
    duplicate = db.query(Menu.id).filter(Menu.slug == payload.slug)
    if route:
        duplicate = duplicate.union(db.query(Menu.id).filter(Menu.ruta == route))
    if duplicate.first():
        raise HTTPException(status_code=409, detail="El slug o la ruta ya existe")
    last_sibling = db.query(Menu.orden).filter(Menu.parent_id == payload.parent_id).order_by(Menu.orden.desc()).first()
    order = (last_sibling[0] if last_sibling else 0) + 1
    values = payload.model_dump(exclude={"ruta", "orden"})
    values["icono"] = payload.icono if payload.tipo in {"seccion", "menu"} else None
    menu = Menu(**values, ruta=route, orden=order)
    db.add(menu)
    db.flush()
    audit_change(db, request, actor, "menus", menu.id, after=MenuWrite.model_validate(menu, from_attributes=True).model_dump())
    db.commit()
    db.refresh(menu)
    return MenuOut.model_validate(menu)


@router.put("/admin/menus/{menu_id}", response_model=MenuOut)
def update_menu(
    menu_id: int,
    payload: MenuWrite,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("menus", "editor")),
    request: Request = None,
):
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    if menu.slug in CORE_MENU_ROUTES and payload.slug != menu.slug:
        raise HTTPException(status_code=409, detail="El slug de una ruta implementada no se puede cambiar")
    if menu.slug in CORE_MENU_SLUGS and not payload.is_active:
        raise HTTPException(status_code=409, detail="El estado activo de una opción central no se puede cambiar")
    if payload.tipo != menu.tipo:
        raise HTTPException(status_code=422, detail="El nivel de una opcion existente no se puede cambiar")
    chain = _ancestor_chain(db, menu.parent_id)
    _validate_hierarchy(db, chain, menu.tipo, slug=menu.slug, moving_id=menu.id)
    route = _menu_route(chain, payload.slug, menu.tipo)
    duplicate = db.query(Menu.id).filter(Menu.id != menu_id, Menu.slug == payload.slug)
    if route:
        duplicate = duplicate.union(
            db.query(Menu.id).filter(Menu.id != menu_id, Menu.ruta == route)
        )
    duplicate = duplicate.first()
    if duplicate:
        raise HTTPException(status_code=409, detail="El slug o la ruta ya existe")
    before = MenuWrite.model_validate(menu, from_attributes=True).model_dump()
    for key, value in payload.model_dump(exclude={"parent_id", "ruta", "orden", "tipo"}).items():
        setattr(menu, key, value)
    if menu.tipo not in {"seccion", "menu"}:
        menu.icono = None
    menu.ruta = route
    _sync_descendant_routes(menu)
    audit_change(db, request, actor, "menus", menu.id, before=before, after=MenuWrite.model_validate(menu, from_attributes=True).model_dump())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El slug o la ruta entra en conflicto con otra opcion")
    db.refresh(menu)
    return MenuOut.model_validate(menu)


@router.patch("/admin/menus/{menu_id}/move", response_model=MenuOut)
def move_menu(
    menu_id: int,
    payload: MenuMove,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("menus", "editor")),
    request: Request = None,
):
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu no encontrado")
    if payload.parent_id == menu_id:
        raise HTTPException(status_code=422, detail="Un menu no puede ser su propio padre")
    if menu.slug == "inicio" and (payload.parent_id is not None or payload.position != 0):
        raise HTTPException(status_code=409, detail="Inicio debe permanecer como primera opcion superior")
    if menu.slug in CORE_MENU_SLUGS and payload.parent_id != menu.parent_id:
        raise HTTPException(status_code=409, detail="Las opciones centrales solo pueden reordenarse dentro de su modulo")
    chain = _ancestor_chain(db, payload.parent_id)
    if any(parent.id == menu_id for parent in chain):
        raise HTTPException(status_code=422, detail="No se puede mover una opcion dentro de uno de sus descendientes")
    _validate_hierarchy(db, chain, menu.tipo, slug=menu.slug, moving_id=menu.id)
    before = MenuWrite.model_validate(menu, from_attributes=True).model_dump()
    previous_parent_id = menu.parent_id
    menu.parent_id = payload.parent_id
    menu.ruta = _menu_route(chain, menu.slug, menu.tipo)
    _sync_descendant_routes(menu)
    if previous_parent_id != payload.parent_id:
        _resequence_siblings(db, previous_parent_id, menu.id, 10_000)
    _resequence_siblings(db, payload.parent_id, menu.id, payload.position)
    db.flush()
    audit_change(db, request, actor, "menus", menu.id, before=before, after=MenuWrite.model_validate(menu, from_attributes=True).model_dump())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El movimiento genera una ruta ya existente")
    db.refresh(menu)
    return MenuOut.model_validate(menu)


@router.delete("/admin/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("menus", "gestor")),
    request: Request = None,
):
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    if menu.slug in CORE_MENU_SLUGS:
        raise HTTPException(status_code=409, detail="Las opciones centrales de ABISSOL no se pueden eliminar")
    audit_change(db, request, actor, "menus", menu.id, before=MenuWrite.model_validate(menu, from_attributes=True).model_dump())
    db.delete(menu)
    db.commit()


@router.get("/access-grants", response_model=list[AccessGrantOut])
def list_access_grants(
    role_id: int | None = Query(default=None),
    usuario_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("accesos", "lector")),
):
    query = db.query(AccessGrant)
    if role_id is not None:
        query = query.filter(AccessGrant.role_id == role_id)
    if usuario_id is not None:
        query = query.filter(AccessGrant.usuario_id == usuario_id)
    return query.order_by(AccessGrant.menu_id, AccessGrant.id).all()


def _grant_for_subject(db: Session, payload: AccessGrantWrite, menu_id: int) -> AccessGrant | None:
    query = db.query(AccessGrant).filter(AccessGrant.menu_id == menu_id)
    return query.filter(
        AccessGrant.role_id == payload.role_id
        if payload.role_id is not None
        else AccessGrant.usuario_id == payload.usuario_id
    ).first()


def _grant_snapshot(grant: AccessGrant) -> dict:
    return AccessGrantWrite.model_validate(grant, from_attributes=True).model_dump()


def _write_subject_grant(
    db: Session,
    payload: AccessGrantWrite,
    menu_id: int,
    actor: Usuario,
    request: Request | None,
    *,
    access_level: str,
    starts_at=None,
    ends_at=None,
    is_active: bool = True,
) -> AccessGrant:
    grant = _grant_for_subject(db, payload, menu_id)
    before = _grant_snapshot(grant) if grant else None
    values = {
        "role_id": payload.role_id,
        "usuario_id": payload.usuario_id,
        "menu_id": menu_id,
        "access_level": access_level,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "is_active": is_active,
    }
    if grant is None:
        grant = AccessGrant(**values, created_by=actor.id, updated_by=actor.id)
        db.add(grant)
    else:
        for key, value in values.items():
            setattr(grant, key, value)
        grant.updated_by = actor.id
        grant.updated_at = utc_now()
    db.flush()
    after = _grant_snapshot(grant)
    if before != after:
        audit_change(db, request, actor, "access_grants", grant.id, before=before, after=after)
    return grant


def _descendant_ids(db: Session, menu_id: int) -> list[int]:
    by_parent: dict[int, list[int]] = {}
    for child_id, parent_id in db.query(Menu.id, Menu.parent_id).filter(Menu.parent_id.is_not(None)).all():
        by_parent.setdefault(parent_id, []).append(child_id)
    descendants: list[int] = []
    pending = list(by_parent.get(menu_id, []))
    while pending:
        child_id = pending.pop(0)
        descendants.append(child_id)
        pending.extend(by_parent.get(child_id, []))
    return descendants


@router.put("/access-grants", response_model=AccessGrantOut)
def upsert_access_grant(
    payload: AccessGrantWrite,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("accesos", "editor")),
    request: Request = None,
):
    menu = db.get(Menu, payload.menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    if menu.tipo == "seccion":
        raise HTTPException(status_code=422, detail="Las secciones son contenedores; administra el acceso en sus módulos y opciones")
    if payload.role_id is not None and not db.get(Rol, payload.role_id):
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if payload.usuario_id is not None and not db.get(Usuario, payload.usuario_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    grant = _write_subject_grant(
        db, payload, menu.id, actor, request,
        access_level=payload.access_level,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
    )
    if payload.access_level == "none":
        for descendant_id in _descendant_ids(db, menu.id):
            _write_subject_grant(
                db, payload, descendant_id, actor, request,
                access_level="none",
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                is_active=payload.is_active,
            )
    else:
        for ancestor in _ancestor_chain(db, menu.parent_id):
            if ancestor.tipo == "seccion":
                continue
            current = _grant_for_subject(db, payload, ancestor.id)
            if current is not None and current.access_level != "none":
                continue
            _write_subject_grant(
                db, payload, ancestor.id, actor, request,
                access_level="lector",
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                is_active=payload.is_active,
            )
    db.commit()
    db.refresh(grant)
    return grant


@router.delete("/access-grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_access_grant(
    grant_id: int,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("accesos", "gestor")),
    request: Request = None,
):
    grant = db.get(AccessGrant, grant_id)
    if not grant:
        raise HTTPException(status_code=404, detail="Acceso no encontrado")
    audit_change(db, request, actor, "access_grants", grant.id, before=AccessGrantWrite.model_validate(grant, from_attributes=True).model_dump())
    db.delete(grant)
    db.commit()
