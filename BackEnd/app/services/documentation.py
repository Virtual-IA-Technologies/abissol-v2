import json
import re
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.documentation import DocArticle, DocComment, DocRevision
from ..utils.time import utc_iso, utc_now

DOC_ROOT = Path(__file__).resolve().parents[3] / "docs" / "ia-agentica"
STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "documentation"
FIELDS = ("titulo", "resumen", "categoria", "audiencia", "estado", "contenido")
MAX_REPOSITORY_DOC_CHARS = 1_000_000


def programmer(user):
    return any(role.es_superusuario for role in user.active_roles())


def visible_articles(db, user):
    query = db.query(DocArticle)
    if not programmer(user):
        query = query.filter(DocArticle.estado == "publicado", DocArticle.audiencia == "general")
    return query


def article_for(db, user, article_id, *, lock=False):
    query = visible_articles(db, user).filter(DocArticle.id == article_id)
    article = (query.with_for_update() if lock else query).first()
    if article is None:
        raise HTTPException(404, "Artículo no encontrado")
    return article


def snapshot(article, *, content=True):
    data = {field: getattr(article, field) for field in FIELDS if content or field != "contenido"}
    data.update(id=article.id, version=article.version, origen=article.origen,
                ruta_fuente=article.ruta_fuente, actualizado_en=utc_iso(article.actualizado_en))
    return data


def revision(db, article, user, reason):
    db.flush()
    db.add(DocRevision(articulo_id=article.id, version=article.version,
                       usuario_id=user.id if user else None,
                       autor=f"{user.nombre} {user.apellido}" if user else "Sincronización del proyecto",
                       motivo=reason, snapshot=json.dumps(snapshot(article), ensure_ascii=False)))


def filter_articles(query, search="", category="", audience="", state=""):
    words = search.strip().split()[:8]
    if words:
        comment_match = query.session.query(DocComment.id).filter(
            DocComment.articulo_id == DocArticle.id, DocComment.estado != "eliminado",
            *[or_(*[column.icontains(word, autoescape=True) for column in
                  (DocComment.contenido, DocComment.cita, DocComment.autor)]) for word in words]).exists()
        document_match = and_(*[or_(*[column.icontains(word, autoescape=True) for column in
                                  (DocArticle.titulo, DocArticle.resumen, DocArticle.contenido)]) for word in words])
        query = query.filter(or_(comment_match, document_match))
    if category:
        query = query.filter(DocArticle.categoria == category)
    if audience:
        query = query.filter(DocArticle.audiencia == audience)
    if state:
        query = query.filter(DocArticle.estado == state)
    return query


def sync_repository(db: Session, user=None, request=None):
    # Only this curated documentation tree is imported, never arbitrary server paths.
    from ..routes.audit import audit_change, record_audit
    if not DOC_ROOT.is_dir():
        raise RuntimeError("No está disponible la documentación del proyecto")
    changed = 0
    for path in sorted(DOC_ROOT.rglob("*.md")):
        if path.is_symlink() or not path.resolve().is_relative_to(DOC_ROOT.resolve()):
            continue
        content = path.read_text(encoding="utf-8-sig")
        if len(content) > MAX_REPOSITORY_DOC_CHARS:
            continue
        source = path.relative_to(DOC_ROOT).as_posix()
        article = db.query(DocArticle).filter(DocArticle.ruta_fuente == source).with_for_update().first()
        if article and article.contenido == content:
            continue
        before = snapshot(article) if article else None
        title = re.search(r"^#\s+(.+)$", content, re.M)
        if article is None:
            article = DocArticle(ruta_fuente=source, origen="repositorio")
            db.add(article)
        article.titulo = (title.group(1) if title else path.stem)[:180]
        article.resumen = "Documentación versionada del proyecto"
        article.categoria = source.split("/")[0] if "/" in source else "Índice"
        article.audiencia = "general" if source in {"MANUAL_DE_USO.md", "MANUAL_DOCUMENTACION.md"} else "interna" if any(part in source for part in ("BITACORA", "ESTADO", "PLANTILLAS")) else "tecnica"
        if article.audiencia == "general":
            article.categoria = "Manuales de uso"
            article.resumen = "Guía práctica para usuarios de ABISSOL"
        article.estado = "publicado"
        article.contenido = content
        article.actualizado_en = utc_now()
        revision(db, article, user, "Sincronización de Markdown del proyecto")
        if user:
            audit_change(db, request, user, "doc_articles", article.id, before=before, after=snapshot(article), module="documentacion")
        else:
            record_audit(db, None, "modificar" if before else "crear", "doc_articles", module="documentacion",
                         entity_id=article.id, before=before, after=snapshot(article), detail="Sincronización del proyecto: " + article.titulo)
        changed += 1
    db.commit()
    return changed
