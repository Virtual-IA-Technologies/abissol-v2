import smtplib

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.settings import MessageTemplateSetting, UiSetting
from ..models.user import Usuario
from .email import EmailNotConfigured, send_email
from .whatsapp import WhatsappDeliveryError, WhatsappNotConfigured, send_whatsapp


def _template_settings(db: Session) -> MessageTemplateSetting:
    templates = db.query(MessageTemplateSetting).order_by(MessageTemplateSetting.id).first()
    if templates is None:
        templates = MessageTemplateSetting()
        db.add(templates)
        db.flush()
    return templates


def _context(db: Session, user: Usuario, temporary_password: str) -> dict[str, str]:
    ui = db.query(UiSetting).order_by(UiSetting.id).first()
    organization = (ui.organization_name if ui else "ABISSOL").strip() or "ABISSOL"
    return {
        "nombre": user.nombre,
        "apellido": user.apellido,
        "usuario": user.username,
        "correo": user.correo or "",
        "telefono": user.telefono or "",
        "clave_temporal": temporary_password,
        "organizacion": organization,
        "url_acceso": get_settings().frontend_url,
    }


def _safe_email_failure(exc: Exception) -> str:
    if isinstance(exc, EmailNotConfigured):
        return str(exc)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "El servidor SMTP rechazo el usuario o la clave"
    if isinstance(exc, smtplib.SMTPException):
        return "El servidor SMTP rechazo el mensaje o la configuracion"
    if isinstance(exc, (OSError, TimeoutError)):
        return "No se pudo conectar con el servidor SMTP"
    return "No se pudo completar el envio por correo"


def deliver_user_credentials(
    db: Session,
    user: Usuario,
    temporary_password: str,
    event: str,
    *,
    email_requested: bool,
    whatsapp_requested: bool,
) -> list[dict]:
    templates = _template_settings(db)
    context = _context(db, user, temporary_password)
    if event == "usuarios.crear":
        email_subject = templates.user_created_email_subject
        email_body = templates.user_created_email_body
        whatsapp_body = templates.user_created_whatsapp_body
    elif event == "usuarios.restablecer_clave":
        email_subject = templates.password_reset_email_subject
        email_body = templates.password_reset_email_body
        whatsapp_body = templates.password_reset_whatsapp_body
    else:
        raise ValueError("Evento de credenciales no reconocido")

    results: list[dict] = []
    if email_requested and not user.correo:
        results.append({"canal": "correo", "solicitado": True, "enviado": False, "detalle": "El usuario no tiene correo registrado"})
    elif email_requested:
        try:
            send_email(db, user.correo, email_subject.format_map(context), email_body.format_map(context))
            results.append({"canal": "correo", "solicitado": True, "enviado": True, "detalle": "Correo enviado"})
        except Exception as exc:
            results.append({"canal": "correo", "solicitado": True, "enviado": False, "detalle": _safe_email_failure(exc)})

    if whatsapp_requested:
        if not user.telefono:
            results.append({"canal": "whatsapp", "solicitado": True, "enviado": False, "detalle": "El usuario no tiene telefono"})
        else:
            try:
                send_whatsapp(db, user.telefono, whatsapp_body.format_map(context))
                results.append({"canal": "whatsapp", "solicitado": True, "enviado": True, "detalle": "WhatsApp enviado"})
            except (WhatsappNotConfigured, WhatsappDeliveryError, ValueError) as exc:
                results.append({"canal": "whatsapp", "solicitado": True, "enviado": False, "detalle": str(exc)})
            except Exception:
                results.append({"canal": "whatsapp", "solicitado": True, "enviado": False, "detalle": "No se pudo completar el envio por WhatsApp"})
    return results
