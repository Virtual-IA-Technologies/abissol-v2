from fastapi import HTTPException
from ..schemas.avi_agent import AviAgentResponse
from .avi_conversation import route_message
from .access_control import access_by_slug

async def respond(payload, configuration, db, user):
    if not configuration.enabled:
        raise HTTPException(403, "Asistente desactivado")
    interpretation = route_message(payload, configuration, set(access_by_slug(db, user)))
    return AviAgentResponse(message=interpretation.message or "Utiliza el menú para acceder a las opciones de la plataforma.", source="Asistente de plataforma",
        results=[interpretation.selected_result] if interpretation.selected_result else [])
