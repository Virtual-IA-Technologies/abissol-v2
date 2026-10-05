import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from ..models.settings import SmtpSetting
from ..utils.secrets import decrypt_secret


class EmailNotConfigured(RuntimeError):
    pass


def get_smtp_setting(db: Session) -> SmtpSetting:
    setting = db.query(SmtpSetting).order_by(SmtpSetting.id).first()
    if not setting or not setting.is_active or not setting.host or not setting.from_email:
        raise EmailNotConfigured("Configura y activa SMTP antes de enviar correos")
    return setting


def send_email(
    db: Session,
    recipient: str,
    subject: str,
    text: str,
    html: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    setting = get_smtp_setting(db)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((setting.from_name, setting.from_email))
    message["To"] = recipient
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    for filename, content, mime in attachments or []:
        main_type, _, sub_type = mime.partition("/")
        message.add_attachment(content, maintype=main_type or "application", subtype=sub_type or "octet-stream", filename=filename)

    smtp_class = smtplib.SMTP_SSL if setting.use_ssl else smtplib.SMTP
    with smtp_class(setting.host, setting.port, timeout=15) as client:
        if setting.use_tls and not setting.use_ssl:
            client.starttls()
        if setting.username:
            if not setting.password_encrypted:
                raise EmailNotConfigured("Falta la clave SMTP")
            client.login(setting.username, decrypt_secret(setting.password_encrypted))
        client.send_message(message)
