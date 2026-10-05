import difflib
import io
import json
import posixpath
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Literal
from uuid import uuid4
from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, load_only
from sqlalchemy.orm.exc import StaleDataError

from ..database import get_db
from ..models.documentation import DocArticle, DocAttachment, DocComment, DocRevision
from ..schemas.documentation import ArticleWrite, CommentWrite, RestoreWrite
from ..services import documentation as service
from ..services.access_control import require_access
from ..utils.time import utc_iso, utc_now
from .audit import audit_change

router = APIRouter(prefix="/documentacion")
reader = require_access("documentacion", "lector")


def writer(request: Request, user=Depends(require_access("documentacion", "editor"))):
    if not service.programmer(user) or request.state.auth_identity.impersonation_id:
        raise HTTPException(403, "Solo Programador puede editar documentación, fuera de impersonación")
    return user


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "El artículo cambió. Recarga antes de guardar; tu borrador no fue aplicado.")


def check_version(article, version):
    if article.version != version:
        raise HTTPException(409, "El artículo cambió. Recarga antes de guardar; conserva tu borrador.")


def editable(article):
    if article.origen == "repositorio":
        raise HTTPException(409, "Este documento procede del proyecto. Crea una propuesta de edición y expórtala a Markdown.")


def attachment_out(row):
    return {"id": row.id, "articulo_id": row.articulo_id, "comentario_id": row.comentario_id,
            "nombre": row.nombre, "mime": row.mime, "tamano": row.tamano, "uso": row.uso}


def comment_out(row):
    return {"id": row.id, "articulo_id": row.articulo_id, "usuario_id": row.usuario_id,
            "autor": row.autor, "contenido": row.contenido, "cita": row.cita, "ancla": row.ancla,
            "version_articulo": row.version_articulo, "estado": row.estado, "creado_en": utc_iso(row.creado_en)}


@router.get("")
def index(request: Request, q: str = Query(default="", max_length=100), categoria: str = "", audiencia: str = "", estado: str = "",
          orden: Literal["titulo", "fecha"] = "titulo", pagina: int = Query(default=1, ge=1),
          tamano: int = Query(default=10, ge=0, le=100), db: Session = Depends(get_db), user=Depends(reader)):
    base = service.visible_articles(db, user)
    categories = [r[0] for r in base.with_entities(DocArticle.categoria).distinct().order_by(DocArticle.categoria)]
    query = service.filter_articles(base, q, categoria, audiencia, estado)
    total = query.count()
    query = query.options(load_only(*[getattr(DocArticle, key) for key in
                           ("id", "titulo", "resumen", "categoria", "audiencia", "estado", "origen", "ruta_fuente", "version", "actualizado_en")]))
    query = query.order_by(DocArticle.titulo if orden == "titulo" else DocArticle.actualizado_en.desc(), DocArticle.id)
    if tamano:
        query = query.offset((pagina - 1) * tamano).limit(tamano)
    return {"items": [service.snapshot(a, content=False) for a in query], "total": total,
            "categorias": categories, "puede_editar": service.programmer(user) and not request.state.auth_identity.impersonation_id}


@router.get("/paquete")
def bundle(q: str = Query(default="", max_length=100), categoria: str = "", audiencia: str = "", estado: str = "",
           db: Session = Depends(get_db), user=Depends(reader)):
    rows = service.filter_articles(service.visible_articles(db, user), q, categoria, audiencia, estado).order_by(DocArticle.titulo).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(422, "Filtra una categoría para descargar hasta 500 artículos")
    output = io.BytesIO()
    total_bytes = sum(len(row.contenido.encode("utf-8")) for row in rows)
    if total_bytes > 64 * 1024 * 1024:
        raise HTTPException(422, "Filtra más: el paquete admite hasta 64 MB sin comprimir")
    sources = {row.ruta_fuente: f"{row.id}-v{row.version}.md" for row in rows if row.ruta_fuente}
    attachments_by_article = defaultdict(list)
    if rows:
        attachments = (db.query(DocAttachment)
                       .filter(DocAttachment.articulo_id.in_([row.id for row in rows]), DocAttachment.uso == "articulo")
                       .order_by(DocAttachment.articulo_id, DocAttachment.id))
        for attachment in attachments:
            attachments_by_article[attachment.articulo_id].append(attachment)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        index_lines = ["# Documentación exportada", ""]
        for article in rows:
            name = f"{article.id}-v{article.version}.md"
            content = article.contenido
            for attachment in attachments_by_article[article.id]:
                path = (service.STORAGE_ROOT / attachment.archivo).resolve()
                if not path.is_relative_to(service.STORAGE_ROOT.resolve()) or not path.is_file():
                    raise HTTPException(409, "Un adjunto no está disponible; revisa el almacenamiento antes de exportar")
                total_bytes += path.stat().st_size
                if total_bytes > 64 * 1024 * 1024:
                    raise HTTPException(422, "Filtra más: el paquete admite hasta 64 MB sin comprimir")
                asset = f"adjuntos/{article.id}-{attachment.id}{path.suffix}"
                archive.write(path, asset)
                content = content.replace(f"/documentacion/{article.id}/adjuntos/{attachment.id}", asset)
                index_lines.append(f"  - {attachment.nombre}: {asset}")
            if article.ruta_fuente:
                def rewrite(match):
                    href = match.group(1)
                    source = posixpath.normpath(posixpath.join(posixpath.dirname(article.ruta_fuente), href))
                    return f"]({sources.get(source, href)})"
                content = re.sub(r"\]\(([^)]+\.md)\)", rewrite, content)
            archive.writestr(name, content)
            index_lines.append(f"- [{article.titulo}]({name})")
        archive.writestr("INDICE.md", "\n".join(index_lines))
    return Response(output.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="documentacion.zip"', "Cache-Control": "private, no-store"})


@router.post("/sincronizar")
def sync(request: Request, db: Session = Depends(get_db), user=Depends(writer)):
    return {"actualizados": service.sync_repository(db, user, request)}


@router.get("/resolver")
def resolve(desde: int, ruta: str = Query(max_length=500), db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, desde)
    source = posixpath.normpath(posixpath.join(posixpath.dirname(article.ruta_fuente or ""), ruta))
    target = service.visible_articles(db, user).filter(DocArticle.ruta_fuente == source).first()
    if not target:
        raise HTTPException(404, "Documento no encontrado")
    return {"id": target.id}


@router.post("", status_code=201)
def create(payload: ArticleWrite, request: Request, db: Session = Depends(get_db), user=Depends(writer)):
    article = DocArticle(**payload.model_dump(exclude={"motivo", "version"}))
    db.add(article)
    service.revision(db, article, user, payload.motivo)
    audit_change(db, request, user, "doc_articles", article.id, after=service.snapshot(article), module="documentacion")
    commit(db)
    return service.snapshot(article)


@router.get("/{article_id}/recurso")
def repository_resource(article_id: int, ruta: str = Query(max_length=500), db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id)
    links = [unquote(link.split("#")[0]) for link in re.findall(r"\]\(([^)]+)\)", article.contenido)]
    if article.origen != "repositorio" or not article.ruta_fuente or ruta not in links:
        raise HTTPException(404, "Recurso no disponible")
    base = service.DOC_ROOT.resolve()
    source = base / article.ruta_fuente
    target = source.parent / ruta
    resolved = target.resolve()
    if not resolved.is_relative_to(base) or any(part.is_symlink() for part in [target, *target.parents] if part != base):
        raise HTTPException(404, "Recurso no disponible")
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(resolved.suffix.lower())
    if not mime or not resolved.is_file() or resolved.stat().st_size > 8 * 1024 * 1024:
        raise HTTPException(404, "Recurso no disponible")
    # Reuse signature validation: a misleading extension cannot expose source files.
    if file_type(resolved.read_bytes(), resolved.name) != mime:
        raise HTTPException(404, "Recurso no disponible")
    return FileResponse(resolved, media_type=mime, filename=resolved.name,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{article_id}")
def detail(article_id: int, db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id)
    result = service.snapshot(article)
    result["adjuntos"] = [attachment_out(a) for a in db.query(DocAttachment).filter_by(articulo_id=article.id, uso="articulo")]
    return result


@router.put("/{article_id}")
def update(article_id: int, payload: ArticleWrite, request: Request, db: Session = Depends(get_db), user=Depends(writer)):
    article = service.article_for(db, user, article_id, lock=True)
    editable(article)
    check_version(article, payload.version)
    before = service.snapshot(article)
    for key in service.FIELDS:
        setattr(article, key, getattr(payload, key))
    article.actualizado_en = utc_now()
    service.revision(db, article, user, payload.motivo)
    audit_change(db, request, user, "doc_articles", article.id, before=before, after=service.snapshot(article), module="documentacion")
    commit(db)
    return service.snapshot(article)


@router.delete("/{article_id}")
def archive(article_id: int, request: Request, version: int, db: Session = Depends(get_db), user=Depends(writer)):
    article = service.article_for(db, user, article_id, lock=True)
    editable(article)
    check_version(article, version)
    before = service.snapshot(article)
    article.estado = "archivado"
    article.actualizado_en = utc_now()
    service.revision(db, article, user, "Artículo archivado")
    audit_change(db, request, user, "doc_articles", article.id, before=before, after=service.snapshot(article),
                 module="documentacion", action_override="eliminar")
    commit(db)
    return service.snapshot(article)


@router.post("/{article_id}/propuesta", status_code=201)
def propose(article_id: int, request: Request, db: Session = Depends(get_db), user=Depends(writer)):
    original = service.article_for(db, user, article_id)
    article = DocArticle(**{key: getattr(original, key) for key in service.FIELDS})
    article.estado = "borrador"
    article.origen = "propuesta"
    article.titulo = ("Propuesta: " + original.titulo)[:180]
    article.resumen = ("Propuesta para " + (original.ruta_fuente or original.titulo))[:500]
    db.add(article)
    service.revision(db, article, user, "Propuesta de edición del artículo " + str(original.id))
    audit_change(db, request, user, "doc_articles", article.id, after=service.snapshot(article), module="documentacion")
    commit(db)
    return service.snapshot(article)


@router.get("/{article_id}/revisiones")
def history(article_id: int, pagina: int = Query(default=1, ge=1), db: Session = Depends(get_db), user=Depends(writer)):
    service.article_for(db, user, article_id)
    query = db.query(DocRevision).filter_by(articulo_id=article_id)
    rows = query.options(load_only(DocRevision.id, DocRevision.version, DocRevision.autor, DocRevision.motivo, DocRevision.creado_en)).order_by(DocRevision.version.desc()).offset((pagina - 1) * 20).limit(20)
    return {"total": query.count(), "items": [{"id": r.id, "version": r.version, "autor": r.autor, "motivo": r.motivo, "creado_en": utc_iso(r.creado_en)} for r in rows]}


@router.get("/{article_id}/revisiones/{revision_id}")
def revision_detail(article_id: int, revision_id: int, db: Session = Depends(get_db), user=Depends(writer)):
    service.article_for(db, user, article_id)
    row = db.query(DocRevision).filter_by(id=revision_id, articulo_id=article_id).first()
    if not row:
        raise HTTPException(404, "Revisión no encontrada")
    previous = db.query(DocRevision).filter(DocRevision.articulo_id == article_id, DocRevision.version < row.version).order_by(DocRevision.version.desc()).first()
    after = json.loads(row.snapshot)
    before = json.loads(previous.snapshot) if previous else {}
    diff = "\n".join(difflib.unified_diff(before.get("contenido", "").splitlines(), after["contenido"].splitlines(), fromfile="Anterior", tofile="Esta revisión", lineterm=""))
    return {"antes": before, "despues": after, "diff": diff,
            "campos": [key for key in service.FIELDS if before.get(key) != after.get(key)]}


@router.post("/{article_id}/revisiones/{revision_id}/restaurar")
def restore(article_id: int, revision_id: int, payload: RestoreWrite, request: Request, db: Session = Depends(get_db), user=Depends(writer)):
    row = db.query(DocRevision).filter_by(id=revision_id, articulo_id=article_id).first()
    if not row:
        raise HTTPException(404, "Revisión no encontrada")
    data = json.loads(row.snapshot)
    return update(article_id, ArticleWrite(**{key: data[key] for key in service.FIELDS}, version=payload.version,
                                          motivo=f"Restaurar v{row.version}: {payload.motivo}"[:500]), request, db, user)


@router.get("/{article_id}/exportar")
def export(article_id: int, db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id)
    return Response(article.contenido.encode("utf-8"), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="documento-{article.id}-v{article.version}.md"', "Cache-Control": "no-store"})


@router.get("/{article_id}/comentarios")
def comments(article_id: int, pagina: int = Query(default=1, ge=1), q: str = Query(default="", max_length=100), db: Session = Depends(get_db), user=Depends(reader)):
    service.article_for(db, user, article_id)
    query = db.query(DocComment).filter(DocComment.articulo_id == article_id, DocComment.estado != "eliminado")
    for word in q.strip().split()[:8]:
        query = query.filter(or_(*[column.icontains(word, autoescape=True) for column in (DocComment.contenido, DocComment.cita, DocComment.autor)]))
    rows = query.order_by(DocComment.id.desc()).offset((pagina - 1) * 20).limit(20).all()
    attachments = db.query(DocAttachment).filter(DocAttachment.comentario_id.in_([r.id for r in rows])).all() if rows else []
    return {"total": query.count(), "items": [{**comment_out(row), "adjuntos": [attachment_out(a) for a in attachments if a.comentario_id == row.id]} for row in rows]}


@router.get("/{article_id}/anotaciones")
def annotations(article_id: int, despues: int = Query(default=0, ge=0), db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id)
    rows = db.query(DocComment).options(load_only(DocComment.id, DocComment.cita, DocComment.ancla, DocComment.version_articulo, DocComment.estado)).filter(
        DocComment.articulo_id == article_id, DocComment.estado != "eliminado", DocComment.cita != "",
        DocComment.version_articulo == article.version, DocComment.id > despues).order_by(DocComment.id).limit(101).all()
    return {"items": [{"id": row.id, "cita": row.cita, "ancla": row.ancla, "version_articulo": row.version_articulo, "estado": row.estado} for row in rows[:100]],
            "siguiente": rows[99].id if len(rows) > 100 else None}


@router.get("/{article_id}/comentarios/{comment_id}")
def comment_detail(article_id: int, comment_id: int, db: Session = Depends(get_db), user=Depends(reader)):
    service.article_for(db, user, article_id)
    row = db.query(DocComment).filter_by(id=comment_id, articulo_id=article_id).filter(DocComment.estado != "eliminado").first()
    if not row:
        raise HTTPException(404, "Comentario no encontrado")
    attachments = db.query(DocAttachment).filter_by(comentario_id=row.id).all()
    return {**comment_out(row), "adjuntos": [attachment_out(a) for a in attachments]}


@router.post("/{article_id}/comentarios", status_code=201)
def comment(article_id: int, payload: CommentWrite, request: Request, db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id, lock=True)
    if article.estado == "archivado":
        raise HTTPException(409, "El artículo está archivado")
    check_version(article, payload.version_articulo)
    if payload.ancla and not payload.cita:
        raise HTTPException(422, "El ancla requiere una cita")
    attachments = db.query(DocAttachment).filter(DocAttachment.id.in_(payload.adjuntos)).with_for_update().all() if payload.adjuntos else []
    if len(attachments) != len(set(payload.adjuntos)) or any(a.articulo_id != article_id or a.usuario_id != user.id or a.comentario_id is not None or a.uso != "comentario" for a in attachments):
        raise HTTPException(400, "Adjuntos no válidos para este comentario")
    row = DocComment(articulo_id=article_id, usuario_id=user.id, autor=f"{user.nombre} {user.apellido}",
                     **payload.model_dump(exclude={"adjuntos"}))
    db.add(row)
    db.flush()
    for attachment in attachments:
        before = attachment_out(attachment)
        attachment.comentario_id = row.id
        audit_change(db, request, user, "doc_attachments", attachment.id, before=before, after=attachment_out(attachment), module="documentacion")
    audit_change(db, request, user, "doc_comments", row.id, after={**comment_out(row), "adjuntos": payload.adjuntos}, module="documentacion",
                 detail=f"Comentario creado por {row.autor} en {article.titulo}")
    commit(db)
    return comment_out(row)


@router.patch("/{article_id}/comentarios/{comment_id}")
def moderate(article_id: int, comment_id: int, request: Request, estado: Literal["abierto", "resuelto", "eliminado"], db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id)
    row = db.query(DocComment).filter_by(id=comment_id, articulo_id=article_id).with_for_update().first()
    if not row:
        raise HTTPException(404, "Comentario no encontrado")
    if row.usuario_id != user.id and not service.programmer(user):
        raise HTTPException(403, "Solo el autor o Programador puede gestionar el comentario")
    before = comment_out(row)
    row.estado = estado
    audit_change(db, request, user, "doc_comments", row.id, before=before, after=comment_out(row),
                 module="documentacion", action_override="eliminar" if estado == "eliminado" else None,
                 detail=f"Comentario {estado} en {article.titulo}")
    commit(db)
    return comment_out(row)


def file_type(data, filename):
    suffix = Path(filename).suffix.lower()
    if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if suffix in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if suffix == ".webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        return "application/pdf"
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist() and "[Content_Types].xml" in archive.namelist():
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except zipfile.BadZipFile:
            pass
    if suffix in (".md", ".txt"):
        try:
            data.decode("utf-8-sig")
            if b"\x00" not in data:
                return "text/plain"
        except UnicodeDecodeError:
            pass
    raise HTTPException(422, "Usa PNG, JPG, WebP, PDF, DOCX o texto UTF-8 válido")


@router.post("/{article_id}/adjuntos", status_code=201)
async def upload(article_id: int, request: Request, uso: Literal["articulo", "comentario"] = Form(), file: UploadFile = File(), db: Session = Depends(get_db), user=Depends(reader)):
    article = service.article_for(db, user, article_id)
    if article.estado == "archivado":
        raise HTTPException(409, "El artículo está archivado")
    if uso == "articulo":
        if not service.programmer(user) or request.state.auth_identity.impersonation_id:
            raise HTTPException(403, "Solo Programador puede adjuntar al artículo")
        editable(article)
    name = re.sub(r"[\x00-\x1f\x7f]", "", (file.filename or "archivo").replace("\\", "/").split("/")[-1])[:180]
    data = await file.read(8 * 1024 * 1024 + 1)
    if not data or len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "El archivo debe tener entre 1 byte y 8 MB")
    mime = file_type(data, name)
    if db.query(DocAttachment).filter_by(articulo_id=article_id, usuario_id=user.id).count() >= 100:
        raise HTTPException(409, "Límite de 100 adjuntos por autor y artículo")
    service.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    filename = uuid4().hex + Path(name).suffix.lower()
    path = service.STORAGE_ROOT / filename
    path.write_bytes(data)
    try:
        row = DocAttachment(articulo_id=article_id, usuario_id=user.id, nombre=name, archivo=filename, mime=mime, tamano=len(data), uso=uso)
        db.add(row)
        db.flush()
        audit_change(db, request, user, "doc_attachments", row.id, after=attachment_out(row), module="documentacion")
        commit(db)
        return attachment_out(row)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise


@router.get("/{article_id}/adjuntos/{attachment_id}")
def download(article_id: int, attachment_id: int, db: Session = Depends(get_db), user=Depends(reader)):
    service.article_for(db, user, article_id)
    row = db.query(DocAttachment).filter_by(id=attachment_id, articulo_id=article_id).first()
    if not row:
        raise HTTPException(404, "Archivo no encontrado")
    if row.uso == "comentario":
        comment_row = db.get(DocComment, row.comentario_id) if row.comentario_id else None
        if not comment_row or comment_row.estado == "eliminado":
            if row.usuario_id != user.id and not service.programmer(user):
                raise HTTPException(404, "Archivo no encontrado")
    path = (service.STORAGE_ROOT / row.archivo).resolve()
    if not path.is_relative_to(service.STORAGE_ROOT.resolve()) or not path.is_file():
        raise HTTPException(404, "Archivo no disponible")
    return FileResponse(path, media_type=row.mime, filename=row.nombre, content_disposition_type="attachment",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
