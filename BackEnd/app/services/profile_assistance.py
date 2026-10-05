"""Asistencia del Programador; JWT sigue validando sesión y ambas identidades."""
from fastapi import HTTPException


def authorize_profile(identity):
    if identity.actor_user.id == identity.effective_user.id and not identity.impersonation_id:
        return
    if not identity.impersonation_id or not any(role.es_superusuario for role in identity.actor_user.active_roles()):
        raise HTTPException(403, 'Solo Programador puede asistir al usuario impersonado')
