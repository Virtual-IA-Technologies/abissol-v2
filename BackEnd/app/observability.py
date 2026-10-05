from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request

from .database import SessionLocal
from .models.audit import AuditLog

logger = logging.getLogger("abissol.requests")


def needs_http_audit(method, path, status_code, functional_committed=False):
    if method in {'GET','HEAD','OPTIONS'}:
        return False
    if status_code >= 400:
        return True
    routine = path.endswith('/refresh-session') or path.endswith('/notificaciones/leer-todas') or (
        '/notificaciones/' in path and path.endswith('/leer'))
    return not routine and not functional_committed


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip()[:80] or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    caught: Exception | None = None
    response = None
    try:
        response = await call_next(request)
    except Exception as exc:
        caught = exc
        logger.exception("request_failed method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
    elapsed_ms = (time.perf_counter() - started) * 1000
    status_code = response.status_code if response is not None else 500
    if response is not None:
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
    logger.info(
        "request_completed method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
        request.method, request.url.path, status_code, elapsed_ms, request_id,
    )
    if needs_http_audit(request.method,request.url.path,status_code,getattr(request.state,'functional_audit_committed',False)):
        identity = getattr(request.state, "auth_identity", None)
        db = SessionLocal()
        try:
            path_parts = [part for part in request.url.path.split("/") if part]
            module = path_parts[-2] if len(path_parts) > 1 else "core"
            db.add(AuditLog(
                usuario_id=getattr(identity, "effective_user_id", None),
                actor_usuario_id=getattr(identity, "actor_user_id", None),
                impersonacion_id=getattr(identity, "impersonation_id", None),
                accion=request.method.lower(),
                modulo=module[:80],
                entidad=request.url.path[:80],
                detalle="Movimiento HTTP auditado automáticamente por ABISSOL",
                ip=(request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip() or (request.client.host if request.client else None)),
                user_agent=request.headers.get("user-agent", "")[:255] or None,
                request_id=request_id,
                metodo=request.method,
                ruta=request.url.path[:255],
                estado_http=status_code,
            ))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("audit_failed request_id=%s", request_id)
        finally:
            db.close()
    if caught is not None:
        raise caught
    return response
