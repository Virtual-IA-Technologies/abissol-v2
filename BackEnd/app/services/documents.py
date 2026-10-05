from pathlib import Path
from sqlalchemy import or_, exists, select
from fastapi import HTTPException
from ..models.documents import Document, DocumentFolder, DocumentShare, DocumentVersion
from ..utils.time import utc_iso

STORAGE = Path(__file__).resolve().parents[2] / 'storage/documents'


def visible(db, user):
    # All access, including administrators, is explicit ownership or sharing.
    return db.query(Document).filter(or_(Document.owner_id == user.id, exists().where(
        DocumentShare.document_id == Document.id, DocumentShare.user_id == user.id)))


def get_document(db, user, document_id, *, edit=False, trash=False, lock=False):
    query = visible(db, user).filter(Document.id == document_id)
    if not trash:
        query = query.filter(Document.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    document = query.first()
    if document is None:
        raise HTTPException(404, 'Documento no disponible')
    if edit and document.owner_id != user.id:
        raise HTTPException(403, 'Solo el propietario puede modificar este documento')
    return document


def get_folder(db, user, folder_id, *, trash=False):
    if folder_id is None:
        return None
    folder = db.query(DocumentFolder).filter_by(id=folder_id, owner_id=user.id).first()
    if folder is None or (folder.deleted_at is not None and not trash):
        raise HTTPException(404, 'Carpeta no disponible')
    return folder


def check_revision(document, revision):
    if document.revision != revision:
        raise HTTPException(409, 'El documento cambió. Actualiza antes de guardar.')


def snapshot(document):
    return {key: (utc_iso(value) if key.endswith('_at') and value else value)
            for key in ('id', 'owner_id', 'folder_id', 'title', 'description', 'current_version', 'revision', 'deleted_at', 'updated_at')
            for value in [getattr(document, key)]}


def version_out(version):
    return {key: (utc_iso(value) if key == 'created_at' else value)
            for key in ('id', 'number', 'author_id', 'filename', 'mime', 'size', 'sha256', 'reason', 'created_at', 'processing')
            for value in [getattr(version, key)]}


def row_out(document, version, user):
    return {**snapshot(document), 'file': version_out(version), 'owned': document.owner_id == user.id}


def filtered(db, user, q='', folder=None, view='all', kind=''):
    query = visible(db, user).join(DocumentVersion, (DocumentVersion.document_id == Document.id) & (DocumentVersion.number == Document.current_version))
    query = query.filter(Document.deleted_at.is_not(None) if view == 'trash' else Document.deleted_at.is_(None))
    if view == 'mine':
        query = query.filter(Document.owner_id == user.id)
    if view == 'shared':
        query = query.filter(Document.owner_id != user.id)
    if folder is not None:
        if folder:
            get_folder(db, user, folder, trash=view == 'trash')
        query = query.filter(Document.owner_id == user.id)
        if q.strip() and folder:
            # Resolve the subtree in SQL; never load every folder or query per level.
            branch = select(DocumentFolder.id).where(DocumentFolder.id == folder, DocumentFolder.owner_id == user.id).cte('search_folders', recursive=True)
            children = select(DocumentFolder.id).join(branch, DocumentFolder.parent_id == branch.c.id).where(DocumentFolder.owner_id == user.id)
            if view != 'trash':
                children = children.where(DocumentFolder.deleted_at.is_(None))
            branch = branch.union(children)
            query = query.filter(Document.folder_id.in_(select(branch.c.id)))
        elif not q.strip():
            query = query.filter(Document.folder_id == folder if folder else Document.folder_id.is_(None))
    for term in q.split()[:8]:
        pattern = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(Document.title.ilike(pattern, escape='\\'), Document.description.ilike(pattern, escape='\\'), DocumentVersion.text.ilike(pattern, escape='\\')))
    if kind:
        query = query.filter(DocumentVersion.mime.startswith(kind))
    return query


def file_path(key):
    root = STORAGE.resolve()
    target = root / key
    if not target.resolve().is_relative_to(root) or target.is_symlink() or not target.is_file():
        raise HTTPException(404, 'Archivo no disponible')
    return target
