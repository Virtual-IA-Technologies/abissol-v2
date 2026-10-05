"""Reglas transversales limitadas por Wolverine y privacidad de Calendario."""
from sqlalchemy import cast, Integer, or_, and_
from ..models.notification import Notification
from ..models.calendar import CalendarEvent
from ..models.wolverine import Menu
from .access_control import effective_access, ACCESS_RANK

SOURCE_SLUGS = {'usuarios':'usuarios', 'roles':'roles', 'calendar_events':'calendario'}


def source_predicate(db, user):
    menus = db.query(Menu).filter(Menu.slug.in_(SOURCE_SLUGS.values()), Menu.is_active.is_(True)).all()
    levels = effective_access(db, user, menus)
    permitted = {menu.slug for menu in menus if ACCESS_RANK[levels.get(menu.id,('none',''))[0]] >= 1}
    clauses = []
    for entity, slug in SOURCE_SLUGS.items():
        if slug not in permitted:
            continue
        if entity == 'calendar_events':
            events = db.query(CalendarEvent.id).filter(or_(CalendarEvent.visibilidad=='equipo',CalendarEvent.propietario_id==user.id,CalendarEvent.asignados.any(id=user.id)))
            clauses.append(and_(Notification.entity==entity, cast(Notification.entity_id,Integer).in_(events)))
        else:
            clauses.append(Notification.entity==entity)
    return or_(*clauses) if clauses else Notification.id < 0


def may_receive(db, user, entity, entity_id, *, menus=None, access=None):
    slug=SOURCE_SLUGS.get(entity)
    if not slug:
        return False
    menu=next((row for row in menus if row.slug==slug and row.is_active),None) if menus is not None else db.query(Menu).filter_by(slug=slug,is_active=True).first()
    levels=access if access is not None else effective_access(db,user,[menu]) if menu else {}
    if not menu or ACCESS_RANK[levels.get(menu.id,('none',''))[0]]<1:
        return False
    if entity=='calendar_events':
        event=db.get(CalendarEvent,int(entity_id))
        return bool(event and (event.visibilidad=='equipo' or event.propietario_id==user.id or user.id in {person.id for person in event.asignados}))
    return True


def recipient_matches(user, recipients, participants):
    kind=recipients.get('kind','eligible')
    if kind=='participants':return user.id in participants
    if kind=='administrators':return any(role.es_superusuario for role in user.active_roles())
    if kind=='users':return user.id in recipients.get('ids',[])
    if kind=='roles':return bool({role.id for role in user.active_roles()} & set(recipients.get('ids',[])))
    return kind=='eligible'
