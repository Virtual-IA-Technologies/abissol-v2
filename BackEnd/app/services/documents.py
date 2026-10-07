from pathlib import Path
from sqlalchemy import and_, or_, exists, select, false
from fastapi import HTTPException
from ..models.documents import Document, DocumentFolder, DocumentShare, DocumentVersion, DocumentBinding
from ..utils.time import utc_iso

STORAGE = Path(__file__).resolve().parents[2] / 'storage/documents'


def visible(db, user):
    from .access_control import access_by_slug, ACCESS_RANK
    from ..routes import medical as m
    access=access_by_slug(db,user)
    rules=[]
    sources=[('emission','medical-emissions',m.scope,m.Issuance),('invoice','medical-billing',m.invoice_scope,m.Invoice),
             ('liquidation','medical-liquidations',m.liquidation_scope,m.Liquidation)]
    for source,slug,scope,model in sources:
        if ACCESS_RANK.get(access.get(slug,'none'),0)>=ACCESS_RANK['lector']:
            rules.append(and_(DocumentBinding.source_type==source,DocumentBinding.source_id.in_(scope(db,user).with_entities(model.id).scalar_subquery())))
    if any(ACCESS_RANK.get(access.get(slug,'none'),0)>=ACCESS_RANK['lector'] for slug in ('medical-emissions','medical-plans')):
        rules.append(and_(DocumentBinding.source_type=='plan',DocumentBinding.source_id.in_(db.query(m.Plan.id).scalar_subquery())))
    personal=and_(Document.is_system.is_(False),or_(Document.owner_id==user.id,exists().where(DocumentShare.document_id==Document.id,DocumentShare.user_id==user.id)))
    managed=and_(Document.is_system.is_(True),exists().where(DocumentBinding.document_id==Document.id,or_(*rules) if rules else false()))
    return db.query(Document).filter(or_(personal,managed))


def get_document(db, user, document_id, *, edit=False, trash=False, lock=False):
    query = visible(db, user).filter(Document.id == document_id)
    if not trash:
        query = query.filter(Document.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    document = query.first()
    if document is None:
        raise HTTPException(404, 'Documento no disponible')
    if edit and document.is_system:
        raise HTTPException(403,'Documento administrado por su módulo de origen; no admite cambios manuales')
    if edit and document.owner_id != user.id:
        raise HTTPException(403, 'Solo el propietario puede modificar este documento')
    return document


def folder_query(db,user,trash=False):
    leaves=visible(db,user).filter(Document.is_system.is_(True),Document.deleted_at.is_(None)).with_entities(Document.folder_id).scalar_subquery()
    tree=select(DocumentFolder.id,DocumentFolder.parent_id).where(DocumentFolder.id.in_(leaves)).cte('authorized_document_folders',recursive=True)
    tree=tree.union(select(DocumentFolder.id,DocumentFolder.parent_id).join(tree,DocumentFolder.id==tree.c.parent_id))
    return db.query(DocumentFolder).filter(or_(and_(DocumentFolder.owner_id==user.id,DocumentFolder.system_key.is_(None)),
        DocumentFolder.id.in_(select(tree.c.id)) if not trash else false()))


def get_folder(db, user, folder_id, *, trash=False, edit=True):
    if folder_id is None:
        return None
    folder = folder_query(db,user,trash).filter_by(id=folder_id).first()
    if folder is None or (folder.deleted_at is not None and not trash):
        raise HTTPException(404, 'Carpeta no disponible')
    if edit and folder.system_key:
        raise HTTPException(403,'La carpeta se administra automáticamente desde su módulo de origen')
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
    return {**snapshot(document), 'file': version_out(version), 'owned': document.owner_id == user.id and not document.is_system,'managed':bool(document.is_system)}


def filtered(db, user, q='', folder=None, view='all', kind=''):
    query = visible(db, user).join(DocumentVersion, (DocumentVersion.document_id == Document.id) & (DocumentVersion.number == Document.current_version))
    query = query.filter(Document.deleted_at.is_not(None) if view == 'trash' else Document.deleted_at.is_(None))
    if view == 'mine':
        query = query.filter(Document.owner_id == user.id,Document.is_system.is_(False))
    if view == 'shared':
        query = query.filter(Document.owner_id != user.id,Document.is_system.is_(False))
    if folder is not None:
        if folder==0:query=query.filter(Document.owner_id==user.id,Document.is_system.is_(False))
        if folder:
            get_folder(db, user, folder, trash=view == 'trash',edit=False)
        if q.strip() and folder:
            # Resolve the subtree in SQL; never load every folder or query per level.
            branch = select(DocumentFolder.id).where(DocumentFolder.id == folder).cte('search_folders', recursive=True)
            children = select(DocumentFolder.id).join(branch, DocumentFolder.parent_id == branch.c.id)
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
