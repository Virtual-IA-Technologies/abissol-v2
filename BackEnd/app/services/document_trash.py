"""Permanent removal: commit metadata and cleanup queue before touching bytes."""
import logging
from datetime import timedelta
from fastapi import HTTPException
from ..models.documents import (Document, DocumentVersion, DocumentShare, DocumentNotes,
    DocumentLink, DocumentEditSession, DocumentTrashPolicy, DocumentFileRemoval)
from ..models.document_cloud import CloudSource
from ..routes.audit import audit_change, record_audit
from ..utils.time import utc_now
from . import documents as service


def purge(db, owner_id, items, request=None, user=None, cutoff=None):
    ids = sorted(set(item['id'] for item in items))
    rows = db.query(Document).filter(Document.id.in_(ids), Document.owner_id == owner_id).order_by(Document.id).with_for_update().all()
    revisions = {item['id']: item['revision'] for item in items}
    if len(rows) != len(ids):
        raise HTTPException(404, 'Documento no disponible')
    for row in rows:
        if not row.deleted_at or (cutoff and row.deleted_at > cutoff):
            raise HTTPException(409, 'Solo se eliminan archivos que siguen en Papelera')
        service.check_revision(row, revisions[row.id])
    for row in rows:
        versions = db.query(DocumentVersion).filter_by(document_id=row.id).all()
        version_ids = [v.id for v in versions]
        before = {**service.snapshot(row), 'versions': [service.version_out(v) for v in versions],
                  'shares': [s.user_id for s in db.query(DocumentShare).filter_by(document_id=row.id)],
                  'notes': [{'version_id': n.version_id, 'items': n.items} for n in db.query(DocumentNotes).filter(DocumentNotes.version_id.in_(version_ids))]}
        if user:
            audit_change(db, request, user, 'documents', row.id, before=before, module='documentos')
        else:
            record_audit(db, None, 'eliminar', 'documents', 'Eliminación automática por retención personal', module='documentos', entity_id=row.id, before=before)
        for version in versions:
            db.add(DocumentFileRemoval(storage_key=version.storage_key))
        db.query(DocumentLink).filter(DocumentLink.version_id.in_(version_ids)).delete(synchronize_session=False)
        db.query(DocumentNotes).filter(DocumentNotes.version_id.in_(version_ids)).delete(synchronize_session=False)
        db.query(DocumentEditSession).filter_by(document_id=row.id).delete(synchronize_session=False)
        db.query(DocumentShare).filter_by(document_id=row.id).delete(synchronize_session=False)
        db.query(CloudSource).filter_by(document_id=row.id).update({'document_id': None, 'status': 'removed', 'message': 'Copia local eliminada definitivamente'}, synchronize_session=False)
        db.query(DocumentVersion).filter_by(document_id=row.id).delete(synchronize_session=False)
        db.delete(row)
    db.commit()
    return len(rows)


def cleanup_files(db, limit=100):
    root = service.STORAGE.resolve()
    for entry in db.query(DocumentFileRemoval).order_by(DocumentFileRemoval.storage_key).limit(limit).with_for_update(skip_locked=True).all():
        path = root / entry.storage_key
        if path.is_symlink() or not path.resolve().is_relative_to(root) or path.parent != root:
            logging.getLogger(__name__).error('Clave de limpieza documental inválida')
            continue
        try:
            path.unlink(missing_ok=True)
            db.delete(entry)
        except OSError:
            logging.getLogger(__name__).warning('Limpieza documental pendiente; se reintentará')
    db.commit()


def run_due(factory=None):
    if factory is None:
        from ..database import SessionLocal
        factory = SessionLocal
    with factory() as db:
        policies = [(p.owner_id, p.days) for p in db.query(DocumentTrashPolicy).filter(DocumentTrashPolicy.days > 0)]
    for owner_id, days in policies:
        with factory() as db:
            # Lock the policy against concurrent configuration changes.
            policy = db.query(DocumentTrashPolicy).filter_by(owner_id=owner_id).with_for_update().first()
            if not policy or not policy.days:
                continue
            cutoff = utc_now() - timedelta(days=policy.days)
            rows = db.query(Document).filter(Document.owner_id == owner_id, Document.deleted_at <= cutoff).order_by(Document.id).limit(100).with_for_update(skip_locked=True).all()
            if rows:
                purge(db, owner_id, [{'id': r.id, 'revision': r.revision} for r in rows], cutoff=cutoff)
    with factory() as db:
        cleanup_files(db)
