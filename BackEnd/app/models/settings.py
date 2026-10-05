from sqlalchemy import JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from ..database import Base
from ..utils.time import utc_now


DEFAULT_USER_CREATED_EMAIL_SUBJECT = "Tu cuenta en {organizacion}"
DEFAULT_USER_CREATED_EMAIL_BODY = """Hola {nombre},

Tu usuario ha sido creado en {organizacion}.
Usuario: {usuario}
Clave temporal: {clave_temporal}
Acceso: {url_acceso}

Al ingresar deberas cambiar la clave temporal."""
DEFAULT_USER_CREATED_WHATSAPP_BODY = """Hola {nombre}. Tu usuario en {organizacion} es {usuario} y tu clave temporal es {clave_temporal}.
Ingresa en:
{url_acceso}"""
DEFAULT_PASSWORD_RESET_EMAIL_SUBJECT = "Nueva clave temporal en {organizacion}"
DEFAULT_PASSWORD_RESET_EMAIL_BODY = """Hola {nombre},

Se restablecio tu clave en {organizacion}.
Usuario: {usuario}
Clave temporal: {clave_temporal}
Acceso: {url_acceso}

Al ingresar deberas cambiar la clave temporal."""
DEFAULT_PASSWORD_RESET_WHATSAPP_BODY = """Hola {nombre}. Tu nueva clave temporal en {organizacion} es {clave_temporal}. Usuario: {usuario}.
Ingresa en:
{url_acceso}"""


class UiSetting(Base):
    __tablename__ = "ui_settings"
    __table_args__ = (CheckConstraint("ui_scale BETWEEN 80 AND 120", name="ck_ui_settings_scale"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_title = Column(String(120), nullable=False, default="ABISSOL")
    organization_name = Column(String(160), nullable=False, default="ABISSOL")
    footer_text = Column(String(255), nullable=False, default="ABISSOL")
    primary_color = Column(String(7), nullable=False, default="#2563eb")
    ui_scale = Column(Integer, nullable=False, default=100)
    logo_light = Column(String(255), nullable=True)
    logo_dark = Column(String(255), nullable=True)
    favicon = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class SmtpSetting(Base):
    __tablename__ = "smtp_settings"
    __table_args__ = (CheckConstraint("NOT (use_tls = 1 AND use_ssl = 1)", name="ck_smtp_single_security_mode"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=False, default=587)
    username = Column(String(255), nullable=True)
    password_encrypted = Column(Text, nullable=True)
    from_email = Column(String(255), nullable=True)
    from_name = Column(String(120), nullable=False, default="ABISSOL")
    use_tls = Column(Boolean, nullable=False, default=True)
    use_ssl = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class WhatsappSetting(Base):
    __tablename__ = "whatsapp_settings"
    __table_args__ = (
        CheckConstraint("otp_expiration_seconds BETWEEN 30 AND 3600", name="ck_whatsapp_otp_expiration"),
        CheckConstraint("otp_resend_seconds BETWEEN 10 AND 600", name="ck_whatsapp_otp_resend"),
        CheckConstraint("otp_code_length BETWEEN 4 AND 8", name="ck_whatsapp_otp_length"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(30), nullable=False, default="wablas")
    endpoint = Column(String(500), nullable=False, default="https://texas.wablas.com/api/send-message")
    token_encrypted = Column(Text, nullable=True)
    secret_key_encrypted = Column(Text, nullable=True)
    country_code = Column(String(5), nullable=False, default="51")
    otp_enabled = Column(Boolean, nullable=False, default=False)
    otp_expiration_seconds = Column(Integer, nullable=False, default=300)
    otp_resend_seconds = Column(Integer, nullable=False, default=60)
    otp_code_length = Column(Integer, nullable=False, default=6)
    otp_message = Column(String(500), nullable=False, default="Tu codigo de acceso a ABISSOL es {code}. Vence en {minutes} minutos.")
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class MessageTemplateSetting(Base):
    __tablename__ = "message_template_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_created_email_subject = Column(String(200), nullable=False, default=DEFAULT_USER_CREATED_EMAIL_SUBJECT)
    user_created_email_body = Column(Text, nullable=False, default=DEFAULT_USER_CREATED_EMAIL_BODY)
    user_created_whatsapp_body = Column(Text, nullable=False, default=DEFAULT_USER_CREATED_WHATSAPP_BODY)
    password_reset_email_subject = Column(String(200), nullable=False, default=DEFAULT_PASSWORD_RESET_EMAIL_SUBJECT)
    password_reset_email_body = Column(Text, nullable=False, default=DEFAULT_PASSWORD_RESET_EMAIL_BODY)
    password_reset_whatsapp_body = Column(Text, nullable=False, default=DEFAULT_PASSWORD_RESET_WHATSAPP_BODY)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class AviSetting(Base):
    """Configuracion extensible de AVI; el contrato se valida en los esquemas."""

    __tablename__ = "avi_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    revision = Column(Integer, nullable=False, default=1)
    settings = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class AviThread(Base):
    """Hilo de conversacion persistente por usuario. Un solo registro por usuario; se reemplaza en cada guardado."""

    __tablename__ = "avi_threads"
    __table_args__ = (UniqueConstraint("user_id", name="uq_avi_threads_user"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    messages = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
