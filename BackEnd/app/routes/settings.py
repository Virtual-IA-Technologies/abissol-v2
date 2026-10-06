from pathlib import Path
import smtplib
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.settings import AviSetting, AviThread as AviThreadModel, MessageTemplateSetting, SmtpSetting, UiSetting, WhatsappSetting
from ..models.user import Usuario
from ..schemas.settings import (
    AviChatRequest, AviChatResponse, AviConfiguration, AviInterpretation, AviInterpretRequest,
    AviPublicSettings, AviSettingsOut, AviSettingsWrite,
    AviThread as AviThreadSchema, AviThreadMessage,
    MessageTemplateSettingsOut, MessageTemplateSettingsWrite,
    SmtpSettingOut, SmtpSettingWrite, SmtpTestRequest, UiSettingOut, UiSettingWrite,
    WhatsappSettingOut, WhatsappSettingWrite, WhatsappTestRequest,
)
from ..services.avi_ai import is_available as avi_ai_available, provider_status
from ..services.avi_conversation import route_message
from ..schemas.avi_agent import AviAgentResponse
from ..services.avi_orchestrator import respond as agent_response
from ..services.email import EmailNotConfigured, send_email
from ..services.whatsapp import WhatsappDeliveryError, WhatsappNotConfigured, send_whatsapp
from ..services.access_control import access_by_slug, require_access
from ..utils.jwt import get_current_user
from ..utils.secrets import encrypt_secret
from .audit import audit_change

def communication_programmer(user: Usuario = Depends(get_current_user)):
    if not any(role.nombre.casefold() == "programador" for role in user.active_roles()):
        raise HTTPException(status_code=403, detail="Solo Programador puede configurar los canales de comunicación")
    return user


router = APIRouter()
BRANDING_DIR = Path(__file__).resolve().parents[2] / "storage" / "branding"
ALLOWED_IMAGES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}
MAX_IMAGE_BYTES = 4 * 1024 * 1024


def _matches_image_signature(content: bytes, extension: str) -> bool:
    signatures = {
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        ".ico": content.startswith((b"\x00\x00\x01\x00", b"\x00\x00\x02\x00")),
    }
    return signatures.get(extension, False)


def _get_settings(db: Session) -> UiSetting:
    setting = db.query(UiSetting).order_by(UiSetting.id).first()
    if setting is None:
        setting = UiSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _get_smtp_settings(db: Session) -> SmtpSetting:
    setting = db.query(SmtpSetting).order_by(SmtpSetting.id).first()
    if setting is None:
        setting = SmtpSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _get_whatsapp_settings(db: Session) -> WhatsappSetting:
    setting = db.query(WhatsappSetting).order_by(WhatsappSetting.id).first()
    if setting is None:
        setting = WhatsappSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _get_message_templates(db: Session) -> MessageTemplateSetting:
    setting = db.query(MessageTemplateSetting).order_by(MessageTemplateSetting.id).first()
    if setting is None:
        setting = MessageTemplateSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _default_avi_settings() -> dict:
    return AviConfiguration().model_dump(mode="json")


def _get_avi_settings(db: Session) -> AviSetting:
    setting = db.query(AviSetting).order_by(AviSetting.id).first()
    if setting is None:
        setting = AviSetting(settings=_default_avi_settings())
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _avi_response(setting: AviSetting) -> AviSettingsOut:
    configuration = AviConfiguration.model_validate(setting.settings)
    return AviSettingsOut(
        id=setting.id, revision=setting.revision,
        settings=configuration,
        updated_at=setting.updated_at.isoformat() + "Z",
        provider_status=provider_status(configuration.ai),
    )


@router.get("/avi-settings", response_model=AviSettingsOut)
def avi_settings(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("avi-configuracion", "lector")),
):
    return _avi_response(_get_avi_settings(db))


@router.put("/avi-settings", response_model=AviSettingsOut)
def update_avi_settings(
    payload: AviSettingsWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("avi-configuracion", "editor")),
):
    setting = db.query(AviSetting).order_by(AviSetting.id).with_for_update().first()
    if setting is None:
        setting = AviSetting(settings=_default_avi_settings())
        db.add(setting)
        db.flush()
    if setting.revision != payload.revision:
        raise HTTPException(status_code=409, detail="La configuracion de AVI cambio; vuelve a cargarla")
    before = _avi_response(setting).model_dump(mode="json")
    setting.settings = payload.settings.model_dump(mode="json")
    setting.revision += 1
    db.flush()
    after = _avi_response(setting).model_dump(mode="json")
    audit_change(
        db, request, actor, "avi_settings", setting.id, before=before, after=after,
        module="avi", detail="Configuracion global de AVI actualizada",
    )
    db.commit()
    db.refresh(setting)
    return _avi_response(setting)


@router.get("/avi/contexto", response_model=AviPublicSettings)
def avi_context(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    configuration = AviConfiguration.model_validate(_get_avi_settings(db).settings)
    return AviPublicSettings(
        enabled=configuration.enabled,
        assistant_name=configuration.assistant_name,
        welcome_message=configuration.welcome_message,
        max_results=configuration.max_results,
        capabilities=configuration.capabilities,
        initiative=configuration.initiative,
        ai_enabled=avi_ai_available(configuration.ai),
        quick_prompts=configuration.quick_prompts,
    )


@router.post('/avi/agente', response_model=AviAgentResponse)
async def avi_agent(payload: AviInterpretRequest, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Datos internos; interpretación opcional de la pregunta con consentimiento."""
    configuration = AviConfiguration.model_validate(_get_avi_settings(db).settings)
    return await agent_response(payload, configuration, db, user)


@router.post("/avi/consulta", response_model=AviChatResponse)
async def avi_chat(
    payload: AviChatRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    configuration = AviConfiguration.model_validate(_get_avi_settings(db).settings)
    result = await agent_response(AviInterpretRequest(question=payload.question, history=payload.history), configuration, db, user)
    return AviChatResponse(answered=True, message=result.message, source=result.source)


@router.post("/avi/interpretar", response_model=AviInterpretation)
def interpret_avi_message(
    payload: AviInterpretRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Interpreta contexto y capacidades autorizadas sin ejecutar herramientas ni mutaciones."""
    configuration = AviConfiguration.model_validate(_get_avi_settings(db).settings)
    permissions = set(access_by_slug(db, user))
    return route_message(payload, configuration, permissions)


@router.get("/avi/hilo", response_model=AviThreadSchema)
def get_avi_thread(
    db: Session = Depends(get_db),
    actor: Usuario = Depends(get_current_user),
):
    """Devuelve el hilo persistido del usuario autenticado."""
    row = db.query(AviThreadModel).filter(AviThreadModel.user_id == actor.id).first()
    if row is None:
        return AviThreadSchema()
    configuration = AviConfiguration.model_validate(_get_avi_settings(db).settings)
    max_messages = configuration.ai.max_history_messages * 2  # user+assistant intercalados
    messages = (row.messages or [])[-max_messages:]
    return AviThreadSchema(messages=[AviThreadMessage(**m) for m in messages])


@router.put("/avi/hilo", response_model=AviThreadSchema)
def save_avi_thread(
    payload: AviThreadSchema,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(get_current_user),
):
    """Guarda o reemplaza el hilo del usuario autenticado."""
    row = db.query(AviThreadModel).filter(AviThreadModel.user_id == actor.id).first()
    configuration = AviConfiguration.model_validate(_get_avi_settings(db).settings)
    max_messages = min(40, configuration.ai.max_history_messages * 2)
    serialized = [m.model_dump() for m in payload.messages[-max_messages:]]
    if row is None:
        row = AviThreadModel(user_id=actor.id, messages=serialized)
        db.add(row)
    else:
        row.messages = serialized
    db.commit()
    return AviThreadSchema(messages=[AviThreadMessage(**message) for message in serialized])


@router.delete("/avi/hilo", status_code=204)
def clear_avi_thread(
    db: Session = Depends(get_db),
    actor: Usuario = Depends(get_current_user),
):
    """Elimina el hilo del usuario autenticado."""
    db.query(AviThreadModel).filter(AviThreadModel.user_id == actor.id).delete()
    db.commit()


def _smtp_response(setting: SmtpSetting) -> SmtpSettingOut:
    return SmtpSettingOut(
        id=setting.id, host=setting.host, port=setting.port, username=setting.username,
        from_email=setting.from_email, from_name=setting.from_name,
        use_tls=bool(setting.use_tls), use_ssl=bool(setting.use_ssl), is_active=bool(setting.is_active),
        password_configured=bool(setting.password_encrypted),
    )


def _whatsapp_response(setting: WhatsappSetting) -> WhatsappSettingOut:
    return WhatsappSettingOut(
        id=setting.id, provider=setting.provider, endpoint=setting.endpoint,
        country_code=setting.country_code, otp_enabled=bool(setting.otp_enabled),
        otp_expiration_seconds=setting.otp_expiration_seconds,
        otp_resend_seconds=setting.otp_resend_seconds, otp_code_length=setting.otp_code_length,
        otp_message=setting.otp_message, is_active=bool(setting.is_active),
        token_configured=bool(setting.token_encrypted),
        secret_key_configured=bool(setting.secret_key_encrypted),
    )


def _asset_url(request: Request, filename: str | None) -> str | None:
    return str(request.url_for("branding_file", filename=filename)) if filename else None


def _response(request: Request, setting: UiSetting) -> dict:
    return {
        "id": setting.id,
        "app_title": setting.app_title,
        "organization_name": setting.organization_name,
        "footer_text": setting.footer_text,
        "primary_color": setting.primary_color,
        "ui_scale": setting.ui_scale,
        "logo_light_url": _asset_url(request, setting.logo_light),
        "logo_dark_url": _asset_url(request, setting.logo_dark),
        "favicon_url": _asset_url(request, setting.favicon),
    }


@router.get("/ui-settings", response_model=UiSettingOut)
def public_ui_settings(request: Request, db: Session = Depends(get_db)):
    return _response(request, _get_settings(db))


@router.put("/ui-settings", response_model=UiSettingOut)
def update_ui_settings(
    payload: UiSettingWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("apariencia", "editor")),
):
    setting = _get_settings(db)
    before = UiSettingWrite.model_validate(setting, from_attributes=True).model_dump()
    for key, value in payload.model_dump().items():
        setattr(setting, key, value)
    db.flush()
    audit_change(db, request, actor, "ui_settings", setting.id, before=before, after=payload.model_dump())
    db.commit()
    db.refresh(setting)
    return _response(request, setting)


@router.get("/smtp-settings", response_model=SmtpSettingOut)
def smtp_settings(
    db: Session = Depends(get_db),
    _: Usuario = Depends(communication_programmer),
):
    return _smtp_response(_get_smtp_settings(db))


@router.put("/smtp-settings", response_model=SmtpSettingOut)
def update_smtp_settings(
    payload: SmtpSettingWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(communication_programmer),
):
    setting = _get_smtp_settings(db)
    before = _smtp_response(setting).model_dump()
    values = payload.model_dump(exclude={"password"})
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip()
            if key == "username" and not value:
                value = None
        setattr(setting, key, value)
    if payload.username and not (payload.password or setting.password_encrypted):
        raise HTTPException(status_code=422, detail="Ingresa la clave SMTP")
    if payload.password:
        setting.password_encrypted = encrypt_secret(payload.password)
    db.flush()
    after = _smtp_response(setting).model_dump()
    audit_change(db, request, actor, "smtp_settings", setting.id, before=before, after=after)
    db.commit()
    db.refresh(setting)
    return _smtp_response(setting)


@router.post("/smtp-settings/test")
def test_smtp_settings(
    payload: SmtpTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(communication_programmer),
):
    try:
        send_email(
            db, str(payload.recipient), "Prueba de correo de ABISSOL",
            "La configuración SMTP de ABISSOL funciona correctamente.",
            "<p>La configuración SMTP de <strong>ABISSOL</strong> funciona correctamente.</p>",
        )
    except smtplib.SMTPAuthenticationError as exc:
        raise HTTPException(status_code=502, detail="El servidor SMTP rechazo el usuario o la clave") from exc
    except smtplib.SMTPConnectError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo abrir la conexion SMTP (codigo {exc.smtp_code})") from exc
    except (EmailNotConfigured, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except smtplib.SMTPException as exc:
        raise HTTPException(status_code=502, detail="El servidor SMTP rechazo el mensaje o la configuracion") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="El servidor SMTP rechazó la conexión o las credenciales") from exc
    audit_change(
        db, request, actor, "smtp_test", None,
        before=None, after={"recipient": str(payload.recipient), "result": "sent"},
    )
    db.commit()
    return {"message": "Correo de prueba enviado"}


@router.get("/whatsapp-settings", response_model=WhatsappSettingOut)
def whatsapp_settings(
    db: Session = Depends(get_db),
    _: Usuario = Depends(communication_programmer),
):
    return _whatsapp_response(_get_whatsapp_settings(db))


@router.put("/whatsapp-settings", response_model=WhatsappSettingOut)
def update_whatsapp_settings(
    payload: WhatsappSettingWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(communication_programmer),
):
    setting = _get_whatsapp_settings(db)
    before = _whatsapp_response(setting).model_dump()
    for key, value in payload.model_dump(exclude={"token", "secret_key"}).items():
        setattr(setting, key, value.strip() if isinstance(value, str) else value)
    if payload.token:
        setting.token_encrypted = encrypt_secret(payload.token.strip())
    if payload.secret_key:
        setting.secret_key_encrypted = encrypt_secret(payload.secret_key.strip())
    if setting.is_active and (not setting.token_encrypted or not setting.secret_key_encrypted):
        raise HTTPException(status_code=422, detail="Configura el token y la clave secreta antes de activar WhatsApp")
    db.flush()
    after = _whatsapp_response(setting).model_dump()
    audit_change(db, request, actor, "whatsapp_settings", setting.id, before=before, after=after)
    db.commit()
    db.refresh(setting)
    return _whatsapp_response(setting)


@router.post("/whatsapp-settings/test")
def test_whatsapp_settings(
    payload: WhatsappTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(communication_programmer),
):
    try:
        send_whatsapp(db, payload.phone, payload.message.strip())
    except (WhatsappNotConfigured, WhatsappDeliveryError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="No se pudo completar el envio con el proveedor de WhatsApp",
        ) from exc
    digits = "".join(character for character in payload.phone if character.isdigit())
    audit_change(
        db, request, actor, "whatsapp_test", None,
        before=None, after={"phone_suffix": "***" + digits[-3:], "result": "sent"},
    )
    db.commit()
    return {"message": "Mensaje de prueba enviado"}


@router.get("/message-templates", response_model=MessageTemplateSettingsOut)
def message_templates(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_access("plantillas", "lector")),
):
    return _get_message_templates(db)


@router.put("/message-templates", response_model=MessageTemplateSettingsOut)
def update_message_templates(
    payload: MessageTemplateSettingsWrite,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("plantillas", "editor")),
):
    setting = _get_message_templates(db)
    before = MessageTemplateSettingsOut.model_validate(setting).model_dump(exclude={"id"})
    for key, value in payload.model_dump().items():
        setattr(setting, key, value)
    db.flush()
    audit_change(
        db, request, actor, "message_template_settings", setting.id,
        before=before, after=payload.model_dump(),
        detail="Plantillas de credenciales actualizadas",
    )
    db.commit()
    db.refresh(setting)
    return setting


async def _store_image(upload: UploadFile | None, field: str) -> str | None:
    if upload is None or not upload.filename:
        return None
    extension = ALLOWED_IMAGES.get(upload.content_type or "")
    if extension is None:
        raise HTTPException(status_code=422, detail=f"Formato no permitido para {field}")
    content = await upload.read(MAX_IMAGE_BYTES + 1)
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail=f"{field} debe pesar como máximo 4 MB")
    if not _matches_image_signature(content, extension):
        raise HTTPException(status_code=422, detail=f"El contenido de {field} no coincide con su formato")
    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{field}-{uuid4().hex}{extension}"
    (BRANDING_DIR / filename).write_bytes(content)
    return filename


@router.post("/ui-settings/branding", response_model=UiSettingOut)
async def upload_branding(
    request: Request,
    logo_light: UploadFile | None = File(default=None),
    logo_dark: UploadFile | None = File(default=None),
    favicon: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_access("apariencia", "editor")),
):
    if not any((logo_light, logo_dark, favicon)):
        raise HTTPException(status_code=422, detail="Selecciona al menos una imagen")
    setting = _get_settings(db)
    before = {field: getattr(setting, field) for field in ("logo_light", "logo_dark", "favicon")}
    for field, upload in (("logo_light", logo_light), ("logo_dark", logo_dark), ("favicon", favicon)):
        filename = await _store_image(upload, field)
        if filename:
            setattr(setting, field, filename)
    after = {field: getattr(setting, field) for field in ("logo_light", "logo_dark", "favicon")}
    audit_change(db, request, actor, "ui_settings_branding", setting.id, before=before, after=after)
    db.commit()
    db.refresh(setting)
    return _response(request, setting)


@router.get("/branding/{filename}", name="branding_file")
def branding_file(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    path = BRANDING_DIR / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
