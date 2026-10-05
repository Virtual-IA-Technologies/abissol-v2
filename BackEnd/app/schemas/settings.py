from urllib.parse import urlparse

from string import Formatter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UiSettingWrite(BaseModel):
    app_title: str = Field(min_length=2, max_length=120)
    organization_name: str = Field(min_length=2, max_length=160)
    footer_text: str = Field(min_length=2, max_length=255)
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class UiSettingOut(UiSettingWrite):
    # Historical global value retained for read compatibility; clients use personal scale.
    ui_scale: int = 100
    id: int
    logo_light_url: str | None = None
    logo_dark_url: str | None = None
    favicon_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SmtpSettingWrite(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=512)
    from_email: EmailStr
    from_name: str = Field(default="ABISSOL", min_length=1, max_length=120)
    use_tls: bool = True
    use_ssl: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def security_mode(self):
        if self.use_tls and self.use_ssl:
            raise ValueError("Selecciona TLS o SSL, no ambos")
        return self


class SmtpSettingOut(BaseModel):
    id: int
    host: str | None
    port: int
    username: str | None
    from_email: str | None
    from_name: str
    use_tls: bool
    use_ssl: bool
    is_active: bool
    password_configured: bool


class SmtpTestRequest(BaseModel):
    recipient: EmailStr


class WhatsappSettingWrite(BaseModel):
    endpoint: str = Field(default="https://texas.wablas.com/api/send-message", min_length=10, max_length=500)
    token: str | None = Field(default=None, max_length=1000)
    secret_key: str | None = Field(default=None, max_length=1000)
    country_code: str = Field(default="51", pattern=r"^[1-9][0-9]{0,4}$")
    otp_enabled: bool = False
    otp_expiration_seconds: int = Field(default=300, ge=30, le=3600)
    otp_resend_seconds: int = Field(default=60, ge=10, le=600)
    otp_code_length: int = Field(default=6, ge=4, le=8)
    otp_message: str = Field(min_length=10, max_length=500)
    is_active: bool = False

    @field_validator("endpoint")
    @classmethod
    def secure_endpoint(cls, value: str) -> str:
        value = value.strip()
        if not value.lower().startswith("https://"):
            raise ValueError("El endpoint de WhatsApp debe usar HTTPS")
        hostname = (urlparse(value).hostname or "").lower()
        if hostname != "wablas.com" and not hostname.endswith(".wablas.com"):
            raise ValueError("El endpoint debe pertenecer al dominio wablas.com")
        path = urlparse(value).path.rstrip("/").lower()
        if not (path.endswith("/api/send-message") or path.endswith("/api/v2/send-message")):
            raise ValueError("El endpoint debe terminar en /api/send-message o /api/v2/send-message")
        return value

    @field_validator("otp_message")
    @classmethod
    def otp_template(cls, value: str) -> str:
        value = value.strip()
        if "{code}" not in value:
            raise ValueError("La plantilla OTP debe incluir {code}")
        return value


class WhatsappSettingOut(BaseModel):
    id: int
    provider: str
    endpoint: str
    country_code: str
    otp_enabled: bool
    otp_expiration_seconds: int
    otp_resend_seconds: int
    otp_code_length: int
    otp_message: str
    is_active: bool
    token_configured: bool
    secret_key_configured: bool


class WhatsappTestRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    message: str = Field(default="Prueba de WhatsApp de ABISSOL", min_length=1, max_length=1000)


TEMPLATE_VARIABLES = {
    "nombre", "apellido", "usuario", "correo", "telefono",
    "clave_temporal", "organizacion", "url_acceso",
}


class MessageTemplateSettingsWrite(BaseModel):
    user_created_email_subject: str = Field(min_length=1, max_length=200)
    user_created_email_body: str = Field(min_length=10, max_length=4000)
    user_created_whatsapp_body: str = Field(min_length=10, max_length=1000)
    password_reset_email_subject: str = Field(min_length=1, max_length=200)
    password_reset_email_body: str = Field(min_length=10, max_length=4000)
    password_reset_whatsapp_body: str = Field(min_length=10, max_length=1000)

    @field_validator(
        "user_created_email_subject", "user_created_email_body", "user_created_whatsapp_body",
        "password_reset_email_subject", "password_reset_email_body", "password_reset_whatsapp_body",
    )
    @classmethod
    def valid_template(cls, value: str) -> str:
        value = value.strip()
        try:
            parsed = list(Formatter().parse(value))
        except ValueError as exc:
            raise ValueError("La plantilla contiene llaves incompletas") from exc
        for _, field_name, format_spec, conversion in parsed:
            if field_name is not None and field_name not in TEMPLATE_VARIABLES:
                label = field_name or "vacia"
                raise ValueError(f"Variable no permitida: {{{label}}}")
            if format_spec or conversion:
                raise ValueError("Las variables no admiten formatos ni conversiones")
        return value

    @model_validator(mode="after")
    def temporary_password_is_present(self):
        bodies = (
            self.user_created_email_body, self.user_created_whatsapp_body,
            self.password_reset_email_body, self.password_reset_whatsapp_body,
        )
        if any("{clave_temporal}" not in body for body in bodies):
            raise ValueError("Cada mensaje debe incluir {clave_temporal}")
        return self


class MessageTemplateSettingsOut(MessageTemplateSettingsWrite):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AviCapabilities(BaseModel):
    navigation: bool = True
    notifications: bool = True
    documentation: bool = True
    document_management: bool = True
    document_analysis: bool = False


class AviInitiative(BaseModel):
    enabled: bool = True
    daily_summary: bool = True
    daily_summary_time: str = Field(default="08:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = Field(default="20:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    quiet_hours_end: str = Field(default="07:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    minimum_severity: Literal["info", "warning", "critical"] = "info"
    cooldown_minutes: int = Field(default=60, ge=5, le=1440)


class AviAISettings(BaseModel):
    enabled: bool = False
    providers: list[Literal["gemini", "groq", "mistral"]] = Field(
        default_factory=lambda: ["gemini", "groq", "mistral"], min_length=1, max_length=3,
    )
    gemini_model: str = Field(default="gemini-2.5-flash-lite", min_length=2, max_length=120)
    groq_model: str = Field(default="llama-3.1-8b-instant", min_length=2, max_length=120)
    mistral_model: str = Field(default="mistral-small-latest", min_length=2, max_length=120)
    # Indica que el usuario autorizó enviar la conversación a un proveedor externo.
    external_ai_consent: bool = False
    # Consentimiento separado: permite enviar fragmentos de documentos autorizados.
    external_document_consent: bool = False
    max_output_tokens: int = Field(default=500, ge=100, le=4000)
    timeout_seconds: int = Field(default=20, ge=5, le=60)
    max_history_messages: int = Field(default=8, ge=2, le=20)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_field(cls, data: object) -> object:
        """Compatibilidad hacia atrás: lee allow_internal_data si external_ai_consent no existe."""
        if isinstance(data, dict) and "external_ai_consent" not in data and "allow_internal_data" in data:
            data = dict(data)
            data["external_ai_consent"] = data.pop("allow_internal_data")
        return data

    @model_validator(mode="after")
    def valid_provider(self):
        if self.external_document_consent:
            raise ValueError('AVI consulta documentos internamente; el envío externo de documentos no está disponible')
        if len(self.providers) != len(set(self.providers)):
            raise ValueError("La cadena de proveedores no admite duplicados")
        if self.external_ai_consent and not self.enabled:
            raise ValueError("No se puede autorizar IA externa con la IA desactivada")
        if self.external_document_consent and not self.external_ai_consent:
            raise ValueError("El analisis externo de documentos requiere autorizar primero la conversacion")
        return self


class AviQuickPrompt(BaseModel):
    """Botón de acceso rápido visible en el panel de AVI."""
    label: str = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=2, max_length=200)
    # Nombre de la capacidad en AviCapabilities que debe estar activa (None = siempre visible).
    capability: Literal["navigation", "notifications", "documentation", "document_management", "document_analysis"] | None = None
    # Slug Wolverine que el usuario debe poseer (None = sin restricción adicional).
    wolverine_slug: str | None = None


class AviConfiguration(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    enabled: bool = False
    assistant_name: str = Field(default="AVI", min_length=2, max_length=40)
    welcome_message: str = Field(
        default="Hola, soy AVI. Puedo guiarte por ABISSOL y ayudarte con tus avisos y archivos.",
        min_length=10, max_length=300,
    )
    max_results: int = Field(default=6, ge=3, le=20)
    capabilities: AviCapabilities = Field(default_factory=AviCapabilities)
    initiative: AviInitiative = Field(default_factory=AviInitiative)
    ai: AviAISettings = Field(default_factory=AviAISettings)
    quick_prompts: list[AviQuickPrompt] = Field(
        default_factory=lambda: [
            AviQuickPrompt(label="Opciones", prompt="opciones disponibles", capability="navigation"),
            AviQuickPrompt(label="Documentos", prompt="documentos", capability="document_management", wolverine_slug="documentos"),
            AviQuickPrompt(label="Avisos", prompt="mis notificaciones", capability="notifications", wolverine_slug="notificaciones"),
        ]
    )

    @model_validator(mode="after")
    def valid_document_analysis(self):
        if self.ai.external_document_consent and not self.capabilities.document_analysis:
            raise ValueError("El envio de fragmentos requiere habilitar analisis documental")
        return self


class AviSettingsWrite(BaseModel):
    revision: int = Field(ge=1)
    settings: AviConfiguration


class AviSettingsOut(BaseModel):
    id: int
    revision: int
    settings: AviConfiguration
    updated_at: str
    provider_status: list["AviProviderStatus"] = Field(default_factory=list)


class AviProviderStatus(BaseModel):
    provider: Literal["gemini", "groq", "mistral"]
    configured: bool
    model: str


class AviPublicSettings(BaseModel):
    enabled: bool
    assistant_name: str
    welcome_message: str
    max_results: int
    capabilities: AviCapabilities
    initiative: AviInitiative
    ai_enabled: bool
    quick_prompts: list[AviQuickPrompt] = Field(default_factory=list)


class AviChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)
    capability: str | None = Field(default=None, max_length=80)
    fallback_reason: str | None = Field(default=None, max_length=40)


class AviChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[AviChatMessage] = Field(default_factory=list, max_length=20)
    internal_results_found: bool = False


class AviDocumentSource(BaseModel):
    document_id: int
    title: str
    version: int


class AviChatResponse(BaseModel):
    answered: bool
    message: str | None = None
    source: str
    provider: Literal["gemini", "groq", "mistral"] | None = None
    model: str | None = None
    provider_error: bool = False
    privacy_blocked: bool = False
    attempted_providers: list[str] = Field(default_factory=list)
    document_sources: list[AviDocumentSource] = Field(default_factory=list)


class AviContextResult(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=80)
    kind: Literal["option", "record"]
    title: str = Field(min_length=1, max_length=300)
    subtitle: str = Field(default="", max_length=300)
    url: str = Field(min_length=1, max_length=1000)


class AviInterpretRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[AviChatMessage] = Field(default_factory=list, max_length=20)
    context_results: list[AviContextResult] = Field(default_factory=list, max_length=20)


class AviCapabilityCandidate(BaseModel):
    capability: str
    display_name: str
    score: float = Field(ge=0, le=1)


class AviInterpretation(BaseModel):
    capability: str | None = None
    source: Literal["context", "exact", "semantic", "llm", "fallback"]
    routing_confidence: float = Field(default=0, ge=0, le=1)
    entity_confidence: float = Field(default=0, ge=0, le=1)
    parameter_confidence: float = Field(default=0, ge=0, le=1)
    context_confidence: float = Field(default=0, ge=0, le=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    candidates: list[AviCapabilityCandidate] = Field(default_factory=list, max_length=5)
    requires_clarification: bool = False
    fallback_reason: Literal[
        "MISSING_ENTITY", "MISSING_PARAMETER", "MULTIPLE_MATCHES", "LOW_CONFIDENCE",
        "UNSUPPORTED_CAPABILITY", "PERMISSION_DENIED", "NO_RESULTS", "PROVIDER_FAILURE",
        "CONTEXT_CONFLICT",
    ] | None = None
    message: str | None = Field(default=None, max_length=1000)
    no_results_message: str | None = Field(default=None, max_length=1000)
    selected_result: AviContextResult | None = None


class AviThreadMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)
    results: list[AviContextResult] = Field(default_factory=list, max_length=20)
    capability: str | None = Field(default=None, max_length=80)
    fallback_reason: str | None = Field(default=None, max_length=40)


class AviThread(BaseModel):
    messages: list[AviThreadMessage] = Field(default_factory=list, max_length=40)
