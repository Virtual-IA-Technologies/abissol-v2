import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session, aliased
from sqlalchemy import event

from ..database import get_db
from ..models.audit import AuditLog
from ..models.user import Usuario
from ..services.access_control import require_access
from ..services.analytics import audit_statistics
from ..services.notifications import publish_audit_notification
from ..utils.time import utc_iso

router = APIRouter()


@router.get('/auditoria/archivo')
def archive_status(db: Session=Depends(get_db),user=Depends(require_access('auditoria','lector'))):
    from ..services.audit_retention import eligible_query,list_archives,RETENTION_DAYS
    eligible=db.scalar(func.count().select().select_from(eligible_query().subquery()))
    return {'eligible':eligible,'days':RETENTION_DAYS,'files':list_archives(),
            'can_archive':any(r.es_superusuario for r in user.active_roles())}


@router.post('/auditoria/archivo')
def archive_technical(request:Request,confirmed:bool=False,db:Session=Depends(get_db),user=Depends(require_access('auditoria','gestor'))):
    if not any(r.es_superusuario for r in user.active_roles()):raise HTTPException(403,'Solo Programador puede archivar')
    if not confirmed:raise HTTPException(422,'Confirme el archivo de eventos técnicos antiguos')
    from ..services.audit_retention import archive_due
    try:
        count=archive_due(db)
        if count:audit_change(db,request,user,'audit_archive','http',after={'archived':count},module='auditoria',detail=f'Archivados {count} HTTP exitosos antiguos en archivo comprimido verificado')
        db.commit()
        return {'archived':count}
    except Exception:
        db.rollback()
        raise


@router.get('/auditoria/archivo/{filename}')
def download_archive(filename:str,user=Depends(require_access('auditoria','lector'))):
    import re
    from ..services.audit_retention import ARCHIVE_ROOT
    if not re.fullmatch(r'\d{8}T\d{6}-\d+-\d+-[a-f0-9]{32}\.jsonl\.gz',filename):raise HTTPException(404,'Archivo no disponible')
    path=ARCHIVE_ROOT/filename
    if not path.is_file() or path.is_symlink():raise HTTPException(404,'Archivo no disponible')
    return FileResponse(path,filename=filename,media_type='application/gzip',headers={'Cache-Control':'private, no-store'})


@event.listens_for(Session, 'after_commit')
def _committed_audit_requests(session):
    if session.in_nested_transaction(): return
    for request in session.info.pop('functional_audit_requests', []):
        request.state.functional_audit_committed = True


@event.listens_for(Session, 'after_rollback')
def _rollback_audit_requests(session):
    session.info.pop('functional_audit_requests', None)

SENSITIVE_AUDIT_KEYS = {
    "authorization", "cookie", "contrasena", "password", "token", "access_token",
    "refresh_token", "secret", "secret_key", "smtp_password", "api_key", "private_key",
}


@router.get("/auditoria/estadisticas")
def get_audit_statistics(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("auditoria", "lector")),
):
    return audit_statistics(db, days)


def _record_label(snapshot) -> str:
    if not isinstance(snapshot, dict):
        return ""
    full_name = " ".join(str(snapshot.get(key, "")).strip() for key in ("nombre", "apellido")).strip()
    username = str(snapshot.get("username", "")).strip()
    title = str(snapshot.get("titulo", "")).strip()
    label = full_name or title or str(snapshot.get("slug", "")).strip()
    return f"{label} (@{username})" if label and username else label or (f"@{username}" if username else "")


def _change_detail(action: str, entity: str, entity_id: str | int, snapshot) -> str:
    subject = {
        "usuarios": "Usuario", "roles": "Rol", "calendar_events": "Evento",
        "calendar_labels": "Etiqueta", "menus": "Opcion", "access_grants": "Acceso",
    }.get(entity, entity.replace("_", " ").capitalize())
    verb = {"crear": "creado", "modificar": "modificado", "eliminar": "eliminado"}[action]
    return f"{subject} {verb}: {_record_label(snapshot) or entity_id}"


def audit_change(db: Session, request: Request | None, user: Usuario, entity: str,
                 entity_id: str | int, *, before=None, after=None, module: str = "abissol_core",
                 detail: str | None = None, action_override: str | None = None) -> None:
    """Snapshot en la misma transacción del cambio; nunca incluir contraseñas."""
    if before is not None and after is not None and before == after and not action_override and not any(word in module.lower() for word in ('contab','account')):
        # Una operación sin cambios no requiere dos eventos vacíos. Solo marcar
        # la solicitud después del commit; un rollback conserva el HTTP de fallo.
        if request:db.info.setdefault('functional_audit_requests',[]).append(request)
        return
    identity = getattr(request.state, "auth_identity", None) if request else None
    action = action_override or ("crear" if before is None else "eliminar" if after is None else "modificar")
    if action not in {"crear", "modificar", "eliminar"}:
        raise ValueError("Acción de auditoría no reconocida")
    detail = detail or _change_detail(action, entity, entity_id, after if after is not None else before)
    client_ip = request.client.host if request and request.client else None
    record_audit(
        db, user.id, action,
        entity, actor_id=identity.actor_user.id if identity else user.id,
        impersonation_id=identity.impersonation_id if identity else None,
        module=module, entity_id=entity_id,
        request_id=getattr(request.state, "request_id", None) if request else None,
        method=request.method if request else None,
        path=request.url.path if request else None,
        ip=client_ip,
        user_agent=request.headers.get("user-agent") if request else None,
        before=before, after=after, detail=detail,
    )
    if request:
        db.info.setdefault('functional_audit_requests', []).append(request)
    request_id = getattr(request.state, "request_id", None) if request else None
    publish_audit_notification(
        db,
        action,
        entity,
        entity_id,
        detail,
        actor_id=user.id,
        dedupe_key=f"audit:{request_id}:{entity}:{action}:{entity_id}" if request_id else None,
    )


def _sanitize_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[PROTEGIDO]" if str(key).lower() in SENSITIVE_AUDIT_KEYS else _sanitize_snapshot(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_snapshot(item) for item in value]
    return value


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(_sanitize_snapshot(value), ensure_ascii=False, default=str, separators=(",", ":"))


def record_audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    detail: str = "",
    ip: str | None = None,
    *,
    actor_id: int | None = None,
    impersonation_id: int | None = None,
    module: str = "core",
    entity_id: str | int | None = None,
    request_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    before: Any = None,
    after: Any = None,
    user_agent: str | None = None,
) -> None:
    db.add(AuditLog(
        usuario_id=user_id,
        actor_usuario_id=actor_id or user_id,
        impersonacion_id=impersonation_id,
        accion=action[:80],
        modulo=module[:80],
        entidad=entity[:80],
        entidad_id=str(entity_id)[:80] if entity_id is not None else None,
        detalle=detail,
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
        request_id=(request_id or "")[:80] or None,
        metodo=method,
        ruta=(path or "")[:255] or None,
        estado_http=status_code,
        datos_antes=_json(before),
        datos_despues=_json(after),
    ))


@router.get("/auditoria")
def list_audit(
    page: int = Query(default=1, ge=1),
    page_size: str = Query(default="10", pattern=r"^(10|25|50|all)$"),
    search: str = Query(default="", max_length=200),
    filter_by: str = Query(default="all", pattern=r"^(all|create|update|delete|errors)$"),
    sort_key: str = Query(default="date", pattern=r"^(date|actor|action)$"),
    direction: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("auditoria", "lector")),
):
    actor = aliased(Usuario)
    query = db.query(AuditLog).outerjoin(actor, actor.id == AuditLog.actor_usuario_id)
    term = search.strip().lower()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(
            func.lower(AuditLog.accion).like(pattern),
            func.lower(AuditLog.modulo).like(pattern),
            func.lower(AuditLog.entidad).like(pattern),
            func.lower(AuditLog.entidad_id).like(pattern),
            func.lower(AuditLog.detalle).like(pattern),
            func.lower(AuditLog.metodo).like(pattern),
            func.lower(AuditLog.ruta).like(pattern),
            cast(AuditLog.estado_http, String).like(pattern),
            func.lower(actor.nombre).like(pattern),
            func.lower(actor.apellido).like(pattern),
            func.lower(actor.username).like(pattern),
        ))
    action = func.lower(AuditLog.accion)
    if filter_by == "create":
        query = query.filter(action.like("%crear%"))
    elif filter_by == "update":
        query = query.filter(action.like("%modificar%"))
    elif filter_by == "delete":
        query = query.filter(action.like("%eliminar%"))
    elif filter_by == "errors":
        query = query.filter(AuditLog.estado_http >= 400)

    total = query.count()
    order_columns = {
        "date": (AuditLog.creado_en, AuditLog.id),
        "actor": (actor.nombre, actor.apellido, AuditLog.id),
        "action": (AuditLog.accion, AuditLog.id),
    }[sort_key]
    order_by = [column.asc() if direction == "asc" else column.desc() for column in order_columns]
    query = query.order_by(*order_by)
    if page_size != "all":
        size = int(page_size)
        query = query.offset((page - 1) * size).limit(size)
    rows = query.all()
    user_ids = {
        user_id
        for row in rows
        for user_id in (row.actor_usuario_id, row.usuario_id)
        if user_id is not None
    }
    users = {
        user.id: f"{user.nombre} {user.apellido} (@{user.username})"
        for user in db.query(Usuario).filter(Usuario.id.in_(user_ids)).all()
    } if user_ids else {}
    items = [
        {
            "id": row.id,
            "usuario_id": row.usuario_id,
            "actor_usuario_id": row.actor_usuario_id,
            "realizado_por": users.get(row.actor_usuario_id, "Sistema"),
            "usuario_efectivo": users.get(row.usuario_id, "Sistema") if row.usuario_id else "Sistema",
            "impersonacion_id": row.impersonacion_id,
            "accion": row.accion,
            "modulo": row.modulo,
            "entidad": row.entidad,
            "entidad_id": row.entidad_id,
            "detalle": row.detalle,
            "ip": row.ip,
            "request_id": row.request_id,
            "metodo": row.metodo,
            "ruta": row.ruta,
            "estado_http": row.estado_http,
            "datos_antes": row.datos_antes,
            "datos_despues": row.datos_despues,
            "creado_en": utc_iso(row.creado_en),
        }
        for row in rows
    ]
    create_condition = func.lower(AuditLog.accion).like("%crear%")
    update_condition = func.lower(AuditLog.accion).like("%modificar%")
    delete_condition = func.lower(AuditLog.accion).like("%eliminar%")
    count_row = db.query(
        func.count(AuditLog.id),
        func.coalesce(func.sum(case((create_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((update_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((delete_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((AuditLog.estado_http >= 400, 1), else_=0)), 0),
    ).one()
    return {
        "items": items,
        "total": total,
        "counts": {
            "all": int(count_row[0]), "create": int(count_row[1]), "update": int(count_row[2]),
            "delete": int(count_row[3]), "errors": int(count_row[4]),
        },
    }
