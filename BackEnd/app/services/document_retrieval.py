from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import or_

from ..models.documents import Document, DocumentTextChunk, DocumentVersion
from .access_control import access_by_slug
from .documents import visible


STOPWORDS = {
    "archivo", "archivos", "documento", "documentos", "contenido", "explica", "explicar",
    "analiza", "analizar", "resumen", "resume", "este", "esta", "estos", "estas", "sobre",
    "para", "como", "cual", "quiero", "puedes", "favor", "dime", "del", "las", "los", "una",
}
MAX_CONTEXT_CHARS = 12000
MAX_CHUNKS = 6


@dataclass(frozen=True)
class RetrievedDocument:
    document_id: int
    title: str
    version: int
    position: int
    content: str


def _fold(value: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(character) != "Mn"
    )


def search_terms(question: str) -> list[str]:
    values = re.findall(r"[a-z0-9]{3,}", _fold(question))
    return list(dict.fromkeys(value for value in values if value not in STOPWORDS))[:8]


def retrieve(db, user, question: str, titles: list[str] | None = None) -> list[RetrievedDocument]:
    if "documentos" not in access_by_slug(db, user):
        return []
    terms = search_terms(question)
    titles = [title[:180] for title in (titles or []) if title.strip()][:8]
    if not terms and not titles:
        return []

    query = visible(db, user).join(
        DocumentVersion,
        (DocumentVersion.document_id == Document.id) & (DocumentVersion.number == Document.current_version),
    ).join(DocumentTextChunk, DocumentTextChunk.version_id == DocumentVersion.id).filter(
        Document.deleted_at.is_(None), DocumentVersion.processing == "indexed",
    )
    conditions = []
    mysql_fulltext = bool(db.bind and db.bind.dialect.name in {"mysql", "mariadb"} and terms)
    if titles:
        conditions.append(Document.title.in_(titles))
    for term in terms:
        pattern = "%" + term.replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(Document.title.ilike(pattern, escape="\\"))
        if not mysql_fulltext:
            conditions.append(DocumentTextChunk.content.ilike(pattern, escape="\\"))
    match = DocumentTextChunk.content.match(" ".join(terms)) if mysql_fulltext else None
    if match is not None:
        conditions.append(match)
    query = query.filter(or_(*conditions))

    if match is not None:
        query = query.order_by(match.desc(), Document.updated_at.desc(), DocumentTextChunk.position)
    else:
        query = query.order_by(Document.updated_at.desc(), DocumentTextChunk.position)

    rows = query.with_entities(
        Document.id, Document.title, DocumentVersion.number, DocumentTextChunk.position, DocumentTextChunk.content,
    ).limit(MAX_CHUNKS * 3).all()
    result: list[RetrievedDocument] = []
    total = 0
    for document_id, title, version, position, content in rows:
        excerpt = content[:2500]
        if total + len(excerpt) > MAX_CONTEXT_CHARS:
            excerpt = excerpt[:max(0, MAX_CONTEXT_CHARS - total)]
        if not excerpt:
            break
        result.append(RetrievedDocument(document_id, title, version, position, excerpt))
        total += len(excerpt)
        if len(result) >= MAX_CHUNKS or total >= MAX_CONTEXT_CHARS:
            break
    return result
