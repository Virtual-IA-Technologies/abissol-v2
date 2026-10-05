from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, aliased

from ..database import get_db
from ..models.audit import AuditLog
from ..models.calendar import CalendarEvent, CalendarLabel
from ..models.devops import DevopsActionLog
from ..models.rol import Rol
from ..models.settings import SmtpSetting, UiSetting
from ..models.user import Usuario
from ..models.wolverine import AccessGrant, Menu
from ..schemas.search import GlobalSearchResponse, GlobalSearchResult
from ..services.access_control import ACCESS_RANK, access_by_slug, effective_access
from ..services.search_registry import (
    contains_all_search_terms as _contains_all,
    database_search_filter as _database_filter,
    get_search_providers,
    normalize_search_text as _plain,
    register_search_provider,
    search_result_url as _url,
)
from ..utils.jwt import get_current_user

router = APIRouter()
SOURCE_LIMIT = 6


@register_search_provider("usuarios")
def _search_users(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    rows = db.query(Usuario).filter(Usuario.deleted_at.is_(None), _database_filter(
        [Usuario.nombre, Usuario.apellido, Usuario.username, Usuario.correo, Usuario.telefono], terms,
    )).order_by(Usuario.is_active.desc(), Usuario.nombre, Usuario.apellido).limit(SOURCE_LIMIT).all()
    return [GlobalSearchResult(
        id=f"usuario:{row.id}", source="Usuarios", kind="record",
        title=f"{row.nombre} {row.apellido}",
        subtitle=f"@{row.username} · {row.correo}" + (" · Inactivo" if not row.is_active else ""),
        url=_url("/plataforma/administracion/usuarios", query),
    ) for row in rows]


@register_search_provider("roles")
def _search_roles(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    rows = db.query(Rol).filter(_database_filter([Rol.nombre], terms)).order_by(Rol.nombre).limit(SOURCE_LIMIT).all()
    return [GlobalSearchResult(
        id=f"rol:{row.id}", source="Roles", kind="record", title=row.nombre,
        subtitle=f"Prioridad {row.prioridad}" + (" · Inactivo" if not row.is_active else ""),
        url=_url("/plataforma/administracion/roles", query),
    ) for row in rows]


@register_search_provider("accesos")
def _search_access(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    role = aliased(Rol)
    user = aliased(Usuario)
    rows = db.query(AccessGrant, Menu, role, user).join(Menu, Menu.id == AccessGrant.menu_id).outerjoin(
        role, role.id == AccessGrant.role_id,
    ).outerjoin(user, user.id == AccessGrant.usuario_id).filter(_database_filter(
        [Menu.nombre, Menu.slug, AccessGrant.access_level, role.nombre, user.nombre, user.apellido, user.username], terms,
    )).order_by(Menu.nombre, AccessGrant.id).limit(SOURCE_LIMIT).all()
    results = []
    for grant, menu, grant_role, grant_user in rows:
        subject = grant_role.nombre if grant_role else f"{grant_user.nombre} {grant_user.apellido}"
        extra = {"tipo": "rol", "id": grant.role_id} if grant.role_id else {"tipo": "usuario", "id": grant.usuario_id}
        results.append(GlobalSearchResult(
            id=f"acceso:{grant.id}", source="Accesos", kind="record",
            title=f"{subject} → {menu.nombre}", subtitle=f"Nivel {grant.access_level}",
            url=_url("/plataforma/administracion/accesos", menu.nombre, **extra),
        ))
    return results


@register_search_provider("auditoria")
def _search_audit(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    rows = db.query(AuditLog).filter(_database_filter(
        [
            AuditLog.accion, AuditLog.modulo, AuditLog.entidad, AuditLog.entidad_id,
            AuditLog.detalle, AuditLog.ruta, AuditLog.metodo, AuditLog.ip,
            cast(AuditLog.estado_http, String),
        ], terms,
    )).order_by(AuditLog.creado_en.desc(), AuditLog.id.desc()).limit(SOURCE_LIMIT).all()
    return [GlobalSearchResult(
        id=f"auditoria:{row.id}", source="Auditoría", kind="record",
        title=f"{row.estado_http or '—'} · {row.accion} · {row.entidad}",
        subtitle=" · ".join(value for value in [row.metodo, row.ruta, row.detalle, row.ip] if value),
        url=_url("/plataforma/sistema/auditoria", query),
    ) for row in rows]


@register_search_provider("calendario")
def _search_calendar(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    rows = db.query(CalendarEvent).filter(or_(
        _database_filter([CalendarEvent.titulo, CalendarEvent.descripcion, CalendarEvent.ubicacion, CalendarEvent.estado], terms),
        CalendarEvent.etiquetas.any(_database_filter([CalendarLabel.nombre], terms)),
    )).order_by(CalendarEvent.inicio.desc()).limit(SOURCE_LIMIT).all()
    return [GlobalSearchResult(
        id=f"calendario:{row.id}", source="Calendario", kind="record", title=row.titulo,
        subtitle=f"{row.estado.replace('_', ' ').title()} · {row.inicio.isoformat(sep=' ', timespec='minutes')}",
        url=_url("/plataforma/sistema/calendario", query, evento=row.id),
    ) for row in rows]


@register_search_provider("devops")
def _search_devops(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    rows = db.query(DevopsActionLog).filter(_database_filter(
        [DevopsActionLog.accion, DevopsActionLog.estado, DevopsActionLog.mensaje, DevopsActionLog.commit_hash], terms,
    )).order_by(DevopsActionLog.creado_en.desc(), DevopsActionLog.id.desc()).limit(SOURCE_LIMIT).all()
    return [GlobalSearchResult(
        id=f"devops:{row.id}", source="DevOps", kind="record",
        title=f"{row.accion} · {row.estado}", subtitle=row.mensaje,
        url=_url("/plataforma/sistema/devops", query, seccion="historial"),
    ) for row in rows]


@register_search_provider("apariencia")
def _search_appearance(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    row = db.query(UiSetting).order_by(UiSetting.id).first()
    if not row or not _contains_all([row.app_title, row.organization_name, row.footer_text, row.primary_color], terms):
        return []
    return [GlobalSearchResult(
        id=f"apariencia:{row.id}", source="Configuración", kind="record",
        title="Plataforma", subtitle=f"{row.app_title} · {row.organization_name}",
        url="/plataforma/sistema/configuracion/apariencia",
    )]


@register_search_provider("smtp")
def _search_smtp(db: Session, _user: Usuario, terms: list[str], query: str) -> list[GlobalSearchResult]:
    row = db.query(SmtpSetting).order_by(SmtpSetting.id).first()
    if not row or not _contains_all([row.host, row.from_email, row.from_name], terms):
        return []
    return [GlobalSearchResult(
        id=f"smtp:{row.id}", source="Configuración", kind="record", title="Correo SMTP",
        subtitle=f"{row.from_name or 'Remitente'} · {row.host or 'Servidor sin configurar'}",
        url="/plataforma/sistema/configuracion/smtp",
    )]


@router.get("/busqueda-global", response_model=GlobalSearchResponse)
def global_search(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=30, ge=5, le=50),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    query = " ".join(q.split())
    terms = _plain(query).split()[:6]
    menus = db.query(Menu).filter(Menu.is_active.is_(True)).all()
    resolved = effective_access(db, user, menus)
    access = access_by_slug(db, user, resolved, menus)
    results = [GlobalSearchResult(
        id=f"opcion:{menu.id}", source="Opciones", kind="option", title=menu.nombre,
        subtitle=f"{menu.tipo.capitalize()} · {menu.ruta or menu.slug}", url=menu.ruta or "/inicio",
    ) for menu in menus if menu.is_visible and menu.ruta and menu.id in resolved
      and ACCESS_RANK[resolved[menu.id][0]] >= ACCESS_RANK["lector"]
      and _contains_all([menu.nombre, menu.slug, menu.ruta, menu.tipo], terms)][:SOURCE_LIMIT]
    for provider in get_search_providers():
        if provider.slug is None or provider.slug in access:
            results.extend(provider.load(db, user, terms, query))
    truncated = len(results) > limit
    if "documentacion" in access:
        from ..services.documentation import visible_articles, filter_articles
        from ..models.documentation import DocArticle
        rows = filter_articles(visible_articles(db, user), query).with_entities(
            DocArticle.id, DocArticle.titulo, DocArticle.categoria,
        ).order_by(DocArticle.titulo).limit(SOURCE_LIMIT).all()
        results.extend(GlobalSearchResult(id=f"documentacion:{row.id}", source="Documentación", kind="record",
                       title=row.titulo, subtitle=row.categoria,
                       url="/plataforma/sistema/documentacion?" + urlencode({"articulo": row.id, "buscar": query})) for row in rows)
        truncated = len(results) > limit
    if "documentos" in access:
        from ..services.documents import filtered
        from ..models.documents import Document
        rows = filtered(db, user, query).with_entities(Document.id, Document.title).order_by(Document.title).limit(SOURCE_LIMIT).all()
        results.extend(GlobalSearchResult(id=f"documentos:{row.id}", source="Documentos", kind="record", title=row.title,
                       subtitle="Archivo", url="/documentos/archivos?" + urlencode({"documento": row.id, "buscar": query})) for row in rows)
        truncated = len(results) > limit
    return GlobalSearchResponse(query=query, results=results[:limit], truncated=truncated)
