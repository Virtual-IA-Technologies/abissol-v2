"""Edición y anotaciones autenticadas, sin publicar archivos."""
import io
import zipfile
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.documents import DocumentVersion, DocumentNotes
from ..services import documents as service
from ..services.access_control import access_by_slug, ACCESS_RANK
from ..utils.time import utc_now
from .documents import reader, editor, commit, new_version
from .audit import audit_change

router = APIRouter(prefix='/documentos')


def version_for(db, user, document_id, number, edit=False):
    document = service.get_document(db, user, document_id, edit=edit, lock=edit)
    version = db.query(DocumentVersion).filter_by(document_id=document_id, number=number).first()
    if not version:
        raise HTTPException(404, 'Versión no disponible')
    return document, version


class Mark(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    page: int = Field(ge=1, le=10000)
    kind: Literal['highlight', 'comment']
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    width: float = Field(ge=0, le=1, allow_inf_nan=False)
    height: float = Field(ge=0, le=1, allow_inf_nan=False)
    text: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def valid(self):
        if self.x + self.width > 1.001 or self.y + self.height > 1.001:
            raise ValueError('La anotación excede la página')
        if self.kind == 'comment' and not self.text.strip():
            raise ValueError('Escribe el comentario')
        return self


class NotesWrite(BaseModel):
    revision: int = Field(ge=0)
    items: list[Mark] = Field(max_length=500)


@router.get('/{document_id}/versiones/{number}/notas')
def notes(document_id: int, number: int, db: Session = Depends(get_db), user=Depends(reader)):
    document, version = version_for(db, user, document_id, number)
    row = db.get(DocumentNotes, version.id)
    return {'items': row.items if row else [], 'revision': row.revision if row else 0,
            'can_edit': document.owner_id == user.id and ACCESS_RANK[access_by_slug(db, user).get('documentos', 'none')] >= ACCESS_RANK['editor']}


@router.put('/{document_id}/versiones/{number}/notas')
def save_notes(document_id: int, number: int, payload: NotesWrite, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    _, version = version_for(db, user, document_id, number, edit=True)
    if version.mime != 'application/pdf' and not version.mime.startswith('image/'):
        raise HTTPException(422, 'Este formato no admite marcas visuales')
    if len({m.id for m in payload.items}) != len(payload.items):
        raise HTTPException(422, 'Identificadores de anotación repetidos')
    if version.mime.startswith('image/') and any(m.page != 1 for m in payload.items):
        raise HTTPException(422, 'La imagen solo tiene una página')
    row = db.get(DocumentNotes, version.id)
    if (row.revision if row else 0) != payload.revision:
        raise HTTPException(409, 'Las notas cambiaron. Reabre el visor antes de guardar.')
    before = {'items': row.items, 'revision': row.revision} if row else None
    if row is None:
        row = DocumentNotes(version_id=version.id, author_id=user.id)
        db.add(row)
    row.items = [m.model_dump() for m in payload.items]
    row.author_id, row.updated_at = user.id, utc_now()
    audit_change(db, request, user, 'document_notes', version.id, before=before,
                 after={'items': row.items, 'author_id': user.id, 'version_id': version.id}, module='documentos')
    commit(db)
    return notes(document_id, number, db, user)


class TextWrite(BaseModel):
    text: str = Field(min_length=1, max_length=60000)
    revision: int = Field(ge=1)


@router.put('/{document_id}/texto')
async def edit_text(document_id: int, payload: TextWrite, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    document = service.get_document(db, user, document_id, edit=True)
    version = db.query(DocumentVersion).filter_by(document_id=document_id, number=document.current_version).one()
    if version.mime != 'text/plain':
        raise HTTPException(422, 'Usa el editor correspondiente a este formato')
    file = UploadFile(filename=version.filename, file=io.BytesIO(payload.text.encode('utf-8')))
    return await new_version(document_id, request, file, payload.revision, 'Edición en línea', db, user)


def office_mime(data, name):
    suffix = Path(name).suffix.lower()
    formats = {'.xlsx': ('xl/workbook.xml', 'spreadsheetml.sheet'), '.pptx': ('ppt/presentation.xml', 'presentationml.presentation')}
    if suffix not in formats:
        return None
    entry, mime = formats[suffix]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if entry in archive.namelist() and '[Content_Types].xml' in archive.namelist():
                return 'application/vnd.openxmlformats-officedocument.' + mime
    except zipfile.BadZipFile:
        pass
    raise HTTPException(422, 'Archivo Office inválido')
