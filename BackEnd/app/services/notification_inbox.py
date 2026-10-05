"""Consulta y retirada personal del buzón; ninguna regla concede acceso."""
from fastapi import HTTPException
from sqlalchemy import or_
from ..models.notification import Notification
from ..utils.time import utc_now
from .notifications import notification_out
from .access_control import user_with_roles
from .notification_rules import source_predicate


def inbox(db, user_id, *, unread_only=False, page=1, limit=100, search='', source='', severity=''):
    limit = min(max(limit, 1), 200)
    user = user_with_roles(db, user_id)
    base = db.query(Notification).filter(Notification.usuario_id == user_id, Notification.deleted_at.is_(None), source_predicate(db, user))
    query = base
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    for term in search.split()[:8]:
        pattern = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(Notification.title.ilike(pattern, escape='\\'), Notification.message.ilike(pattern, escape='\\')))
    if source:
        query = query.filter(Notification.source == source)
    if severity:
        query = query.filter(Notification.severity == severity)
    total = query.count()
    rows = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {'items': [notification_out(row) for row in rows], 'total': total,
            'unread': base.filter(Notification.read_at.is_(None)).count(),
            'sources': [name for name, in base.with_entities(Notification.source).distinct().order_by(Notification.source)]}


def remove(db, user_id, ids):
    ids = set(ids)
    if not ids or len(ids) > 200:
        raise HTTPException(422, 'Selecciona entre 1 y 200 avisos')
    rows = db.query(Notification).filter(Notification.usuario_id == user_id, Notification.id.in_(ids), Notification.deleted_at.is_(None)).with_for_update().all()
    if len(rows) != len(ids):
        raise HTTPException(404, 'Un aviso no está disponible en tu buzón')
    now = utc_now()
    for row in rows:
        row.deleted_at = now
    db.commit()
    return {'removed': len(rows)}
