import io
import re
import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Session, defer
from sqlalchemy.orm.exc import StaleDataError
from ..database import get_db
from ..models import Usuario
from ..models.documents import Document, DocumentFolder, DocumentShare, DocumentVersion
from ..services.access_control import require_access
from ..services import documents as service
from ..services.upload_stream import save_document_upload
from ..utils.time import utc_now
from .audit import audit_change

router = APIRouter(prefix='/documentos')
reader = require_access('documentos', 'lector')
editor = require_access('documentos', 'editor')
manager = require_access('documentos', 'gestor')


@router.get('/almacenamiento')
def storage_summary(db:Session=Depends(get_db),user=Depends(reader)):
    # Solo propiedad: no contabilizar ni revelar archivos privados de otros usuarios.
    q=db.query(DocumentVersion).join(Document,Document.id==DocumentVersion.document_id).filter(Document.owner_id==user.id)
    versions,total_bytes,current_bytes,trash_bytes=q.with_entities(func.count(DocumentVersion.id),
        func.coalesce(func.sum(DocumentVersion.size),0),
        func.coalesce(func.sum(case((DocumentVersion.number==Document.current_version,DocumentVersion.size),else_=0)),0),
        func.coalesce(func.sum(case((Document.deleted_at.is_not(None),DocumentVersion.size),else_=0)),0)).one()
    active,trash=db.query(func.coalesce(func.sum(case((Document.deleted_at.is_(None),1),else_=0)),0),
        func.coalesce(func.sum(case((Document.deleted_at.is_not(None),1),else_=0)),0)).filter(Document.owner_id==user.id).one()
    groups=q.filter(Document.deleted_at.is_(None),DocumentVersion.number==Document.current_version).with_entities(
        DocumentVersion.sha256,func.count().label('copies'),func.max(DocumentVersion.size).label('size')).group_by(DocumentVersion.sha256).having(func.count()>1).subquery()
    duplicates,duplicate_bytes=db.query(func.coalesce(func.sum(groups.c.copies-1),0),func.coalesce(func.sum((groups.c.copies-1)*groups.c.size),0)).one()
    return dict(active=int(active),trash=int(trash),versions=int(versions),bytes=int(total_bytes),current_bytes=int(current_bytes),history_bytes=int(total_bytes-current_bytes),trash_bytes=int(trash_bytes),duplicate_copies=int(duplicates),duplicate_bytes=int(duplicate_bytes))


class FolderWrite(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    parent_id: int | None = None

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or any(c in value for c in '/\\') or any(ord(c) < 32 for c in value):
            raise ValueError('Nombre de carpeta inválido')
        return value


class DocumentWrite(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default='', max_length=1000)
    folder_id: int | None = None
    revision: int = Field(ge=1)

    @field_validator('title')
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError('Escribe un título')
        return value.strip()


class NewDocument(FolderWrite):
    document_type: Literal['docx', 'xlsx', 'pptx']
    folder_id: int | None = None


class ShareWrite(BaseModel):
    recipient: str = Field(min_length=1, max_length=180)
    revision: int = Field(ge=1)


class CopyDocument(BaseModel):
    folder_id: int | None = None
    revision: int = Field(ge=1)


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, 'El documento cambió. Actualiza antes de guardar.')


class TrashPolicyWrite(BaseModel):
    days: int = Field(ge=0, le=3650)


class PurgeItem(BaseModel):
    id: int = Field(gt=0)
    revision: int = Field(gt=0)


class PurgeWrite(BaseModel):
    items: list[PurgeItem] = Field(min_length=1, max_length=500)


@router.get('/papelera/configuracion')
def trash_policy(db: Session = Depends(get_db), user=Depends(manager)):
    from ..models.documents import DocumentTrashPolicy
    policy = db.get(DocumentTrashPolicy, user.id)
    return {'days': policy.days if policy else 0}


@router.put('/papelera/configuracion')
def save_trash_policy(payload: TrashPolicyWrite, request: Request, db: Session = Depends(get_db), user=Depends(manager)):
    from ..models.documents import DocumentTrashPolicy
    policy = db.query(DocumentTrashPolicy).filter_by(owner_id=user.id).with_for_update().first()
    before = {'owner_id': user.id, 'days': policy.days if policy else 0}
    if not policy:
        policy = DocumentTrashPolicy(owner_id=user.id)
        db.add(policy)
    policy.days = payload.days
    audit_change(db, request, user, 'document_trash_policies', user.id, before=before, after={'owner_id':user.id, 'days':policy.days}, module='documentos')
    commit(db)
    return {'days': policy.days}


@router.post('/papelera/eliminar')
def purge_trash(payload: PurgeWrite, request: Request, db: Session = Depends(get_db), user=Depends(manager)):
    from ..services.document_trash import purge, cleanup_files
    count = purge(db, user.id, [item.model_dump() for item in payload.items], request=request, user=user)
    cleanup_files(db)
    return {'deleted': count}


@router.get('/carpetas')
def folders(trash: bool = False, db: Session = Depends(get_db), user=Depends(reader)):
    query = db.query(DocumentFolder).filter_by(owner_id=user.id)
    rows = query.filter(DocumentFolder.deleted_at.is_not(None) if trash else DocumentFolder.deleted_at.is_(None)).order_by(DocumentFolder.name, DocumentFolder.id).all()
    visible_ids = {r.id for r in rows}
    return [{'id': r.id, 'name': r.name, 'parent_id': r.parent_id if r.parent_id in visible_ids else None,
             'deleted_at': r.deleted_at.isoformat() if r.deleted_at else None} for r in rows]


@router.post('/carpetas', status_code=201)
def create_folder(payload: FolderWrite, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    parent = service.get_folder(db, user, payload.parent_id)
    depth = 0
    while parent:
        depth += 1
        if depth >= 10:
            raise HTTPException(422, 'Máximo diez niveles de carpetas')
        parent = service.get_folder(db, user, parent.parent_id)
    folder = DocumentFolder(owner_id=user.id, **payload.model_dump())
    db.add(folder)
    db.flush()
    audit_change(db, request, user, 'document_folders', folder.id, after={**payload.model_dump(), 'owner_id': user.id}, module='documentos')
    commit(db)
    return {'id': folder.id, **payload.model_dump()}


@router.delete('/carpetas/{folder_id}', status_code=204)
def delete_folder(folder_id: int, request: Request, db: Session = Depends(get_db), user=Depends(manager)):
    folders = folder_tree(db, user, folder_id)
    if folders[0].deleted_at:
        return
    from ..models.document_cloud import CloudFolder
    ids = [folder.id for folder in folders]
    if db.query(CloudFolder).filter(CloudFolder.folder_id.in_(ids)).first():
        raise HTTPException(409, 'Retira primero los vínculos de Drive de la carpeta y sus subcarpetas')
    documents = db.query(Document).filter(Document.folder_id.in_(ids)).order_by(Document.id).with_for_update().all()
    if any(document.owner_id != user.id for document in documents):
        raise HTTPException(409, 'La carpeta contiene documentos de otro propietario')
    batch, now = uuid4().hex, utc_now()
    for folder in folders:
        if folder.deleted_at:
            continue
        before = folder_snapshot(folder)
        folder.deleted_at, folder.trash_batch = now, batch
        audit_change(db, request, user, 'document_folders', folder.id, before=before, after=folder_snapshot(folder), module='documentos')
    for document in documents:
        if document.deleted_at:
            continue
        before = service.snapshot(document)
        document.deleted_at, document.trash_batch, document.updated_at = now, batch, now
        db.flush()
        audit_change(db, request, user, 'documents', document.id, before=before, after=service.snapshot(document), module='documentos')
    commit(db)


def folder_snapshot(folder):
    return {'id': folder.id, 'name': folder.name, 'parent_id': folder.parent_id, 'owner_id': folder.owner_id,
            'deleted_at': folder.deleted_at.isoformat() if folder.deleted_at else None, 'trash_batch': folder.trash_batch}


def folder_tree(db, user, folder_id):
    root = db.query(DocumentFolder).filter_by(id=folder_id, owner_id=user.id).with_for_update().first()
    if root is None:
        raise HTTPException(404, 'Carpeta no disponible')
    result, level, seen = [root], [root.id], {root.id}
    while level:
        children = db.query(DocumentFolder).filter(DocumentFolder.parent_id.in_(level)).order_by(DocumentFolder.id).with_for_update().all()
        if any(child.owner_id != user.id or child.id in seen for child in children):
            raise HTTPException(409, 'La estructura de la carpeta requiere revisión')
        level = [child.id for child in children]
        seen.update(level)
        result.extend(children)
    return result


@router.post('/carpetas/{folder_id}/restaurar', status_code=204)
def restore_folder(folder_id: int, request: Request, db: Session = Depends(get_db), user=Depends(manager)):
    folders = folder_tree(db, user, folder_id)
    root = folders[0]
    if not root.deleted_at:
        return
    if root.parent_id:
        parent = service.get_folder(db, user, root.parent_id, trash=True)
        if parent.deleted_at:
            raise HTTPException(409, 'Restaura primero la carpeta superior')
    batch = root.trash_batch
    restored = [folder for folder in folders if folder.trash_batch == batch and folder.deleted_at]
    ids = [folder.id for folder in restored]
    documents = db.query(Document).filter(Document.folder_id.in_(ids), Document.trash_batch == batch,
                                          Document.deleted_at.is_not(None)).with_for_update().all()
    if any(document.owner_id != user.id for document in documents):
        raise HTTPException(409, 'La carpeta contiene documentos de otro propietario')
    for folder in restored:
        before = folder_snapshot(folder)
        folder.deleted_at = folder.trash_batch = None
        audit_change(db, request, user, 'document_folders', folder.id, before=before, after=folder_snapshot(folder), module='documentos')
    for document in documents:
        before = service.snapshot(document)
        document.deleted_at = document.trash_batch = None
        document.updated_at = utc_now()
        db.flush()
        audit_change(db, request, user, 'documents', document.id, before=before, after=service.snapshot(document), module='documentos')
    commit(db)


@router.get('')
def index(q: str = Query(default='', max_length=100), folder: int | None = Query(default=None, ge=0),
          view: Literal['all', 'mine', 'shared', 'trash'] = 'all', kind: Literal['', 'application/pdf', 'image/', 'text/', 'application/vnd.'] = '',
          order: Literal['title', 'updated', 'size'] = 'updated', direction: Literal['asc', 'desc'] = 'desc',
          page: int = Query(default=1, ge=1), size: int = Query(default=10, ge=0, le=50),
          db: Session = Depends(get_db), user=Depends(reader)):
    if size not in (0, 10, 25, 50):
        raise HTTPException(422, 'Tamaño de página no permitido')
    query = service.filtered(db, user, q, folder, view, kind)
    total, total_bytes = query.with_entities(func.count(Document.id), func.coalesce(func.sum(DocumentVersion.size), 0)).one()
    if not size and total > 5000:
        raise HTTPException(422, 'Limita los filtros a 5000 documentos para ver o exportar todos')
    column = {'title': Document.title, 'updated': Document.updated_at, 'size': DocumentVersion.size}[order]
    query = query.order_by(column.asc() if direction == 'asc' else column.desc(), Document.id)
    if size:
        query = query.offset((page-1)*size).limit(size)
    return {'items': [service.row_out(d, v, user) for d, v in query.with_entities(Document, DocumentVersion).options(defer(DocumentVersion.text)).all()], 'total': total, 'total_bytes': int(total_bytes)}


async def save_file(db, user, file, document, reason):
    return await save_document_upload(db, user, file, document, reason)


@router.post('', status_code=201)
async def upload(request: Request, file: UploadFile = File(), folder_id: int | None = Form(default=None),
                 db: Session = Depends(get_db), user=Depends(editor)):
    service.get_folder(db, user, folder_id)
    document = Document(owner_id=user.id, folder_id=folder_id, title='Archivo', description='', current_version=1)
    db.add(document)
    db.flush()
    path = None
    try:
        version, path = await save_file(db, user, file, document, 'Carga inicial')
        document.title = version.filename
        db.flush()
        audit_change(db, request, user, 'documents', document.id, after={**service.snapshot(document), 'file': service.version_out(version)}, module='documentos')
        commit(db)
    except Exception:
        db.rollback()
        if path:
            path.unlink(missing_ok=True)
        raise
    return service.row_out(document, version, user)


@router.post('/nuevo', status_code=201)
async def create_document(payload: NewDocument, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    # Plantillas vacías versionadas: no cargar generadores Office en el servidor.
    template = Path(__file__).resolve().parents[1] / 'templates' / 'documents' / ('blank.' + payload.document_type)
    name = payload.name
    if name.lower().endswith('.' + payload.document_type):
        name = name[:-(len(payload.document_type)+1)]
    filename = name[:170] + '.' + payload.document_type
    file = UploadFile(filename=filename, file=io.BytesIO(template.read_bytes()))
    try:
        return await upload(request, file, payload.folder_id, db, user)
    finally:
        await file.close()


@router.get('/{document_id}')
def detail(document_id: int, db: Session = Depends(get_db), user=Depends(reader)):
    document = service.get_document(db, user, document_id, trash=True)
    versions = db.query(DocumentVersion).options(defer(DocumentVersion.text)).filter_by(document_id=document_id).order_by(DocumentVersion.number.desc()).all()
    authors = {person.id: f'{person.nombre} {person.apellido}' for person in db.query(Usuario).filter(Usuario.id.in_({v.author_id for v in versions})).all()}
    shares = []
    if document.owner_id == user.id:
        shares = [{'id': share.id, 'name': f'{person.nombre} {person.apellido}'} for share, person in db.query(DocumentShare, Usuario).join(Usuario, Usuario.id == DocumentShare.user_id).filter(DocumentShare.document_id == document_id).all()]
    return {**service.row_out(document, versions[0], user), 'versions': [{**service.version_out(v), 'author_name': authors.get(v.author_id, 'Usuario')} for v in versions], 'shares': shares}


@router.put('/{document_id}')
def update(document_id: int, payload: DocumentWrite, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    document = service.get_document(db, user, document_id, edit=True, lock=True)
    service.check_revision(document, payload.revision)
    service.get_folder(db, user, payload.folder_id)
    before = service.snapshot(document)
    document.title, document.description, document.folder_id = payload.title, payload.description, payload.folder_id
    document.updated_at = utc_now()
    db.flush()
    audit_change(db, request, user, 'documents', document.id, before=before, after=service.snapshot(document), module='documentos')
    commit(db)
    return detail(document_id, db, user)


@router.post('/{document_id}/copiar', status_code=201)
def copy_document(document_id: int, payload: CopyDocument, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    source = service.get_document(db, user, document_id, lock=True)
    service.check_revision(source, payload.revision)
    service.get_folder(db, user, payload.folder_id)
    original = db.query(DocumentVersion).filter_by(document_id=source.id, number=source.current_version).one()
    source_path = service.file_path(original.storage_key)
    if shutil.disk_usage(service.STORAGE).free < original.size + 512 * 1024 * 1024:
        raise HTTPException(507, 'No hay espacio suficiente para copiar el archivo')
    document = Document(owner_id=user.id, folder_id=payload.folder_id, title=source.title, description=source.description, current_version=1)
    path = None
    try:
        db.add(document)
        db.flush()
        suffix = Path(source.title).suffix[:20]
        stem = source.title[:-len(suffix)] if suffix else source.title
        tag = f' - copia {document.id}'
        document.title = stem[:180-len(tag)-len(suffix)] + tag + suffix
        key = uuid4().hex + Path(original.filename).suffix.lower()
        path = service.STORAGE / key
        with source_path.open('rb') as src, path.open('xb') as dest:
            shutil.copyfileobj(src, dest)
        version = DocumentVersion(document_id=document.id, number=1, author_id=user.id,
            filename=original.filename, storage_key=key, mime=original.mime, size=original.size,
            sha256=original.sha256, reason='Copia de documento', processing=original.processing, text=original.text)
        db.add(version)
        db.flush()
        audit_change(db, request, user, 'documents', document.id,
            after={**service.snapshot(document), 'source_document_id':source.id, 'source_version':original.number, 'file':service.version_out(version)}, module='documentos')
        commit(db)
    except Exception:
        db.rollback()
        if path:
            path.unlink(missing_ok=True)
        raise
    return service.row_out(document, version, user)


@router.post('/{document_id}/versiones', status_code=201)
async def new_version(document_id: int, request: Request, file: UploadFile = File(), revision: int = Form(ge=1), reason: str = Form(min_length=1, max_length=500), db: Session = Depends(get_db), user=Depends(editor)):
    document = service.get_document(db, user, document_id, edit=True, lock=True)
    service.check_revision(document, revision)
    before = service.snapshot(document)
    document.current_version += 1
    document.updated_at = utc_now()
    path = None
    try:
        version, path = await save_file(db, user, file, document, reason)
        db.flush()
        audit_change(db, request, user, 'documents', document.id, before=before, after={**service.snapshot(document), 'file': service.version_out(version)}, module='documentos')
        commit(db)
    except Exception:
        db.rollback()
        if path:
            path.unlink(missing_ok=True)
        raise
    return detail(document_id, db, user)


@router.get('/{document_id}/archivo/{number}')
def download(document_id: int, number: int, preview: bool = False, db: Session = Depends(get_db), user=Depends(reader)):
    service.get_document(db, user, document_id)
    version = db.query(DocumentVersion).filter_by(document_id=document_id, number=number).first()
    if not version:
        raise HTTPException(404, 'Versión no disponible')
    inline = preview and (version.mime.startswith('image/') or version.mime in ('application/pdf', 'text/plain'))
    return FileResponse(service.file_path(version.storage_key), filename=version.filename, media_type=version.mime,
                        content_disposition_type='inline' if inline else 'attachment',
                        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "sandbox; default-src 'none'"})


@router.post('/{document_id}/papelera')
def trash(document_id: int, request: Request, revision: int = Query(ge=1), restore: bool = False, db: Session = Depends(get_db), user=Depends(manager)):
    document = service.get_document(db, user, document_id, edit=True, trash=True, lock=True)
    service.check_revision(document, revision)
    before = service.snapshot(document)
    if restore and document.folder_id:
        parent = service.get_folder(db, user, document.folder_id, trash=True)
        if parent.deleted_at:
            raise HTTPException(409, 'Restaura primero la carpeta que contiene este documento')
    document.deleted_at = None if restore else utc_now()
    document.trash_batch = None
    document.updated_at = utc_now()
    db.flush()
    audit_change(db, request, user, 'documents', document.id, before=before, after=service.snapshot(document), module='documentos')
    commit(db)
    return {'ok': True}


@router.post('/{document_id}/compartir')
def share(document_id: int, payload: ShareWrite, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    document = service.get_document(db, user, document_id, edit=True, lock=True)
    service.check_revision(document, payload.revision)
    recipient = db.query(Usuario).filter(Usuario.deleted_at.is_(None), Usuario.is_active.is_(True), or_(Usuario.username == payload.recipient.strip(), Usuario.correo == payload.recipient.strip())).first()
    if not recipient or recipient.id == user.id:
        raise HTTPException(422, 'Indica otro usuario o correo activo de la plataforma')
    if not db.query(DocumentShare).filter_by(document_id=document_id, user_id=recipient.id).first():
        grant = DocumentShare(document_id=document_id, user_id=recipient.id)
        db.add(grant)
        document.updated_at = utc_now()
        db.flush()
        audit_change(db, request, user, 'document_shares', grant.id, after={'document_id': document_id, 'user_id': recipient.id, 'level': 'lector'}, module='documentos')
        commit(db)
    return detail(document_id, db, user)


@router.get('/{document_id}/destinatarios')
def share_recipients(document_id: int, db: Session = Depends(get_db), user=Depends(editor)):
    service.get_document(db, user, document_id, edit=True)
    people = db.query(Usuario).filter(Usuario.deleted_at.is_(None), Usuario.is_active.is_(True), Usuario.id != user.id).order_by(Usuario.nombre, Usuario.id).all()
    return [{'username': person.username, 'name': f'{person.nombre} {person.apellido}'} for person in people]


@router.delete('/{document_id}/compartir/{share_id}', status_code=204)
def unshare(document_id: int, share_id: int, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    document = service.get_document(db, user, document_id, edit=True, lock=True)
    grant = db.query(DocumentShare).filter_by(document_id=document_id, id=share_id).first()
    if not grant:
        raise HTTPException(404, 'Acceso no disponible')
    audit_change(db, request, user, 'document_shares', grant.id, before={'document_id': document_id, 'user_id': grant.user_id, 'level': 'lector'}, module='documentos')
    db.delete(grant)
    document.updated_at = utc_now()
    commit(db)
