"""Roles de operación; no otorgan administración de la plataforma."""
from ..models import Rol, AccessGrant, Menu

ROLE_NAMES = {"source_admin": "Comercial · Coordinador de origen", "responsible": "Comercial · Vendedor responsable", "emitter": "Comercial · Emisor dependiente"}


def seed_commercial_roles(db):
    roles = {}
    for kind, name in ROLE_NAMES.items():
        role = db.query(Rol).filter_by(nombre=name).first()
        if role is None:
            role = Rol(nombre=name, prioridad=30, es_superusuario=False, is_default=False, is_active=True)
            db.add(role)
            db.flush()
            permissions = {"inicio": "lector", "medical": "lector", "medical-emissions": "editor", "medical-dispatches": "editor", "medical-reports": "lector"}
            if kind != "emitter":
                permissions["medical-liquidations"] = "editor"
            if kind == "source_admin":
                permissions["medical-network"] = "lector"
            for slug, access in permissions.items():
                menu = db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(role_id=role.id, menu_id=menu.id, access_level=access))
        roles[kind] = role
    return roles
