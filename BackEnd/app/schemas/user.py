from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator, model_validator

from .roles import RoleSummary


class RoleValidityWrite(BaseModel):
    is_permanent: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC).replace(tzinfo=None) if value is not None and value.tzinfo is not None else value

    @model_validator(mode="after")
    def validate_period(self):
        if self.is_permanent:
            self.starts_at = None
            self.ends_at = None
        elif self.starts_at is None or self.ends_at is None or self.ends_at <= self.starts_at:
            raise ValueError("Un rol temporal necesita inicio y fin, y el fin debe ser posterior")
        return self


class RoleAssignmentWrite(RoleValidityWrite):
    rol_id: int


class RoleMembershipWrite(RoleValidityWrite):
    pass


class RoleAssignmentOut(BaseModel):
    rol_id: int
    is_permanent: bool
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    rol: RoleSummary

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("starts_at", "ends_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        return value.replace(tzinfo=UTC).isoformat() if value is not None else None


class UserRolePayload(BaseModel):
    role_assignments: list[RoleAssignmentWrite] | None = None
    rol_ids: list[int] | None = None

    @model_validator(mode="after")
    def unique_roles(self):
        values = self.role_assignments
        ids = [item.rol_id for item in values] if values is not None else (self.rol_ids or [])
        if len(ids) != len(set(ids)):
            raise ValueError("No se puede asignar el mismo rol más de una vez")
        return self

    def resolved_assignments(self) -> list[RoleAssignmentWrite] | None:
        if self.role_assignments is not None:
            return self.role_assignments
        if self.rol_ids is not None:
            return [RoleAssignmentWrite(rol_id=role_id) for role_id in self.rol_ids]
        return None


class UsuarioCreate(UserRolePayload):
    nombre: str = Field(min_length=1, max_length=180)
    apellido: str = Field(min_length=1, max_length=50)
    username: str = Field(min_length=3, max_length=40)
    correo: EmailStr
    telefono: str | None = Field(default=None, max_length=20)
    contrasena: str | None = None
    notificar_correo: bool = False
    notificar_whatsapp: bool = False

    @model_validator(mode="after")
    def whatsapp_needs_phone(self):
        if self.notificar_whatsapp and not self.telefono:
            raise ValueError("Para notificar por WhatsApp debes ingresar un telefono")
        return self


class UsuarioUpdate(UserRolePayload):
    nombre: str = Field(min_length=1, max_length=180)
    apellido: str = Field(min_length=0, max_length=50)
    username: str = Field(min_length=1, max_length=40)
    correo: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=20)
    contrasena: str | None = None

    @field_validator('correo', mode='before')
    @classmethod
    def missing_email(cls, value):
        return value or None


class MiCuentaUpdate(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    apellido: str = Field(min_length=1, max_length=50)
    username: str = Field(min_length=3, max_length=40)
    correo: EmailStr
    telefono: str | None = Field(default=None, max_length=20)


class MiCuentaClaveUpdate(BaseModel):
    clave_actual: str = Field(min_length=1, max_length=128)
    nueva_clave: str = Field(min_length=1, max_length=128)
    confirmar_clave: str = Field(min_length=1, max_length=128)


class MiCuentaTemaUpdate(BaseModel):
    tema: Literal["light", "medium", "dark", "virtualia", "lady"]


class ThemeAppearanceCustomization(BaseModel):
    menu_palette: Literal["theme", "custom"] = "theme"
    background_palette: Literal["theme", "custom"] = "theme"
    menu_color: str = Field(default="#075985", pattern=r"^#[0-9a-fA-F]{6}$")
    menu_tone: int = Field(default=50, ge=0, le=100, strict=True)
    background_color: str = Field(default="#f3e8ff", pattern=r"^#[0-9a-fA-F]{6}$")
    background_tone: int = Field(default=50, ge=0, le=100, strict=True)


class MiCuentaPreferenciasUpdate(MiCuentaTemaUpdate):
    escala: int = Field(ge=80, le=120, multiple_of=5, strict=True)
    navigation_layout: Literal["sidebar", "icons", "top"] = "sidebar"
    menu_palette: Literal["theme", "custom"] = "theme"
    background_palette: Literal["theme", "custom"] = "theme"
    menu_color: str = Field(default="#075985", pattern=r"^#[0-9a-fA-F]{6}$")
    menu_tone: int = Field(default=50, ge=0, le=100, strict=True)
    background_color: str = Field(default="#f3e8ff", pattern=r"^#[0-9a-fA-F]{6}$")
    background_tone: int = Field(default=50, ge=0, le=100, strict=True)
    appearance_overrides: dict[Literal["light", "medium", "dark", "virtualia", "lady"], ThemeAppearanceCustomization] = Field(default_factory=dict)


class UsuarioDesactivarRequest(BaseModel):
    fecha_finalizacion: date | None = None


class UsuarioRestablecerClaveRequest(BaseModel):
    notificar_correo: bool = False
    notificar_whatsapp: bool = False


class CredentialNotificationResult(BaseModel):
    canal: Literal["correo", "whatsapp"]
    solicitado: bool
    enviado: bool
    detalle: str


class UsuarioOut(BaseModel):
    @field_validator('correo', mode='before')
    @classmethod
    def empty_missing_email(cls, value):
        return value or ''

    id: int
    nombre: str
    apellido: str
    username: str
    telefono: str | None
    legacy_contact_phone: str | None = None
    correo: str
    avatar_file: str | None = None
    tema: Literal["light", "medium", "dark", "virtualia", "lady"] = "medium"
    menu_palette: Literal["theme", "custom"] = "theme"
    background_palette: Literal["theme", "custom"] = "theme"
    menu_color: str = "#075985"
    menu_tone: int = 50
    background_color: str = "#f3e8ff"
    background_tone: int = 50
    appearance_overrides: dict[str, ThemeAppearanceCustomization] = Field(default_factory=dict)
    navigation_layout: Literal["sidebar", "icons", "top"] = "sidebar"
    escala: int = 100
    fecha_registro: datetime
    fecha_finalizacion: date | None = None
    deleted_at: datetime | None = None
    is_active: bool
    requiere_cambio_clave: bool = False
    roles: list[RoleSummary] = Field(default_factory=list)
    role_assignments: list[RoleAssignmentOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("fecha_registro", "deleted_at", when_used="json")
    def serialize_user_datetime_utc(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.astimezone(UTC).isoformat()


class UsuarioCreateOut(UsuarioOut):
    notificaciones: list[CredentialNotificationResult] = Field(default_factory=list)


class UsuarioRestablecerClaveOut(BaseModel):
    message: str
    clave_temporal: str
    requiere_cambio_clave: bool
    notificaciones: list[CredentialNotificationResult] = Field(default_factory=list)


class CambiarClaveObligatoria(BaseModel):
    nueva_clave: str
    confirmar_clave: str
