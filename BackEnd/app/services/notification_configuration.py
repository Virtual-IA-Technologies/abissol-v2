from fastapi import HTTPException
from ..models.notification import NotificationRule
from ..models.rol import Rol
from ..models.user import Usuario


def programmer(user):
    if not any(role.es_superusuario for role in user.active_roles()):
        raise HTTPException(403,'Solo Programador puede configurar las reglas')


def read(db,user,event_types):
    programmer(user)
    stored={row.event_type:row for row in db.query(NotificationRule)}
    return {'rules':{key:{'recipients':stored[key].recipients if key in stored else {'kind':'eligible','ids':[]},
                         'channels':stored[key].channels if key in stored else ['platform']} for key in event_types},
            'roles':[{'id':role.id,'name':role.nombre} for role in db.query(Rol).filter_by(is_active=True).order_by(Rol.nombre)],
            'users':[{'id':person.id,'name':f'{person.nombre} {person.apellido}'} for person in db.query(Usuario).filter(Usuario.is_active.is_(True),Usuario.deleted_at.is_(None)).order_by(Usuario.nombre)],
            'external_channels_enabled':False}


def save(db,user,payload,event_types,request=None):
    programmer(user)
    if set(payload.rules)-set(event_types):raise HTTPException(422,'Tipo de aviso no reconocido')
    active_users={id for id, in db.query(Usuario.id).filter(Usuario.is_active.is_(True),Usuario.deleted_at.is_(None))}
    active_roles={id for id, in db.query(Rol.id).filter_by(is_active=True)}
    for key,rule in payload.rules.items():
        if set(rule.channels)!={'platform'}:raise HTTPException(409,'Los canales externos todavía no están habilitados')
        allowed=active_users if rule.recipients.kind=='users' else active_roles
        if rule.recipients.kind in ('users','roles') and not set(rule.recipients.ids)<=allowed:raise HTTPException(422,'Destinatario no disponible')
        if rule.recipients.kind=='participants' and not key.startswith('calendar_events.'):raise HTTPException(422,'Participantes aplica a eventos del Calendario')
    before={row.event_type:{'recipients':row.recipients,'channels':row.channels} for row in db.query(NotificationRule)}
    for key,rule in payload.rules.items():
        row=db.get(NotificationRule,key)
        if not row:row=NotificationRule(event_type=key);db.add(row)
        row.recipients=rule.recipients.model_dump();row.channels=rule.channels
    if request:
        from ..routes.audit import audit_change
        after={key:rule.model_dump() for key,rule in payload.rules.items()}
        audit_change(db,request,user,'notification_rules','global',before=before,after={**before,**after})
    db.commit()
    return {'saved':len(payload.rules)}
