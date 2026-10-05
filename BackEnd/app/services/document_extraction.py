from __future__ import annotations

import logging
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.documents import DocumentTextChunk, DocumentVersion
from . import documents

logger = logging.getLogger("abissol.document_extraction")

MAX_EXTRACTED_CHARS = int(os.getenv("DOCUMENT_EXTRACTION_MAX_CHARS", "2000000"))
MAX_PDF_PAGES = int(os.getenv("DOCUMENT_EXTRACTION_MAX_PDF_PAGES", "500"))
MAX_OFFICE_ENTRIES = 5000
MAX_OFFICE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 300
PREVIEW_BYTES = 60000


def _normalize(value: str) -> str:
    return re.sub(r"[ \t\f\v]+", " ", value.replace("\x00", " ")).strip()


def _bounded_join(parts) -> str:
    result: list[str] = []
    length = 0
    for raw in parts:
        part = _normalize(str(raw or ""))
        if not part:
            continue
        remaining = MAX_EXTRACTED_CHARS - length
        if remaining <= 0:
            break
        part = part[:remaining]
        result.append(part)
        length += len(part) + 1
    return "\n".join(result)[:MAX_EXTRACTED_CHARS]


def _office_text(file_path: Path, mime: str) -> str:
    prefixes = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("word/",),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("xl/sharedStrings.xml", "xl/worksheets/"),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ("ppt/slides/",),
    }.get(mime)
    if not prefixes:
        return ""
    with zipfile.ZipFile(file_path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_OFFICE_ENTRIES or sum(item.file_size for item in entries) > MAX_OFFICE_UNCOMPRESSED_BYTES:
            raise ValueError("Office excede los limites seguros de extraccion")
        values: list[str] = []
        extracted = 0
        for item in entries:
            if not item.filename.endswith(".xml") or not any(item.filename.startswith(prefix) for prefix in prefixes):
                continue
            root = ElementTree.fromstring(archive.read(item))
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] in {"t", "v"} and node.text:
                    values.append(node.text)
                    extracted += len(node.text)
                    if extracted >= MAX_EXTRACTED_CHARS:
                        return _bounded_join(values)
        return _bounded_join(values)


def extract_text_from_file(file_path: Path, mime: str) -> tuple[str | None, str]:
    """Extrae texto acotado y devuelve (texto, estado final)."""
    try:
        if mime == "application/pdf":
            import pymupdf as fitz

            with fitz.open(file_path) as document:
                text = _bounded_join(document[index].get_text() for index in range(min(len(document), MAX_PDF_PAGES)))
            return (text, "indexed") if text else (None, "ocr_required")
        if mime in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }:
            text = _office_text(file_path, mime)
            return (text, "indexed") if text else (None, "ocr_required")
        if mime.startswith("text/"):
            text = file_path.read_text(encoding="utf-8", errors="replace")[:MAX_EXTRACTED_CHARS]
            return text, "indexed"
        if mime.startswith("image/"):
            return None, "ocr_required"
        return None, "unsupported"
    except Exception as exc:
        logger.warning("No se pudo extraer %s: %s", file_path.name, type(exc).__name__)
        return None, "error"


def _preview(text: str) -> str:
    return text.encode("utf-8")[:PREVIEW_BYTES].decode("utf-8", errors="ignore")


def _chunks(text: str):
    start = 0
    position = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1
        content = text[start:end].strip()
        if content:
            yield DocumentTextChunk(position=position, content=content, char_start=start, char_end=end)
            position += 1
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def process_document_version(db: Session, version_id: int) -> str | None:
    version = db.get(DocumentVersion, version_id)
    if not version or version.processing not in {"pending", "error", "processing"}:
        return None
    version.processing = "processing"
    db.commit()
    try:
        file_path = documents.file_path(version.storage_key)
        text, status = extract_text_from_file(file_path, version.mime)
        db.query(DocumentTextChunk).filter(DocumentTextChunk.version_id == version.id).delete()
        if text:
            for chunk in _chunks(text):
                chunk.version_id = version.id
                db.add(chunk)
            version.text = _preview(text)
        else:
            version.text = None
        version.processing = status
        db.commit()
        return status
    except Exception:
        db.rollback()
        version = db.get(DocumentVersion, version_id)
        if version:
            version.processing = "error"
            db.commit()
        logger.exception("Fallo al indexar la version documental %s", version_id)
        return "error"


def process_document_version_task(version_id: int) -> str | None:
    with SessionLocal() as db:
        return process_document_version(db, version_id)


def run_due(limit: int = 2) -> int:
    """Procesa pocas versiones por ciclo; pending en base funciona como cola durable."""
    with SessionLocal() as db:
        ids = [row[0] for row in db.query(DocumentVersion.id).filter(
            DocumentVersion.processing == "pending",
        ).order_by(DocumentVersion.id).limit(limit).all()]
        claimed = []
        for version_id in ids:
            changed = db.query(DocumentVersion).filter(
                DocumentVersion.id == version_id, DocumentVersion.processing == "pending",
            ).update({"processing": "processing"}, synchronize_session=False)
            if changed:
                claimed.append(version_id)
        db.commit()
    for version_id in claimed:
        process_document_version_task(version_id)
    return len(claimed)


def recover_interrupted() -> int:
    """Devuelve a la cola trabajos interrumpidos por un cierre del proceso."""
    with SessionLocal() as db:
        count = db.query(DocumentVersion).filter(
            DocumentVersion.processing == "processing",
        ).update({"processing": "pending"}, synchronize_session=False)
        db.commit()
        return count
