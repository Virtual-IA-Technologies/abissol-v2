from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from .user import UsuarioOut

AccessLevel = Literal["none", "lector", "editor", "gestor"]


class MenuWrite(BaseModel):
    parent_id: int | None = None
    nombre: str = Field(min_length=2, max_length=100)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=100)
    ruta: str | None = Field(default=None, max_length=180)
    icono: str | None = Field(default=None, max_length=60)
    tipo: Literal["seccion", "modulo", "menu", "submenu", "pestana"] = "menu"
    orden: int = Field(default=0, ge=0)
    is_visible: bool = True
    is_active: bool = True


class MenuOut(MenuWrite):
    id: int
    access_level: AccessLevel | None = None
    access_source: Literal["superuser", "user", "role"] | None = None
    children: list["MenuOut"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MenuMove(BaseModel):
    parent_id: int | None = None
    position: int = Field(ge=0)


class AccessGrantWrite(BaseModel):
    role_id: int | None = None
    usuario_id: int | None = None
    menu_id: int
    access_level: AccessLevel
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        # Compatibilidad: fechas antiguas sin zona se interpretan como UTC.
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def validate_subject_and_dates(self):
        if (self.role_id is None) == (self.usuario_id is None):
            raise ValueError("Indica exactamente un rol o un usuario")
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("El acceso debe ser permanente o tener fecha de inicio y fin")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial")
        return self


class AccessGrantOut(AccessGrantWrite):
    id: int
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("starts_at", "ends_at", "created_at", "updated_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        return value.replace(tzinfo=UTC).isoformat() if value is not None else None


class ImpersonationOut(BaseModel):
    active: bool = False
    session_id: int | None = None
    actor: UsuarioOut | None = None
    effective_user: UsuarioOut | None = None


class WolverineSession(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut
    requiere_cambio_clave: bool
    access: dict[str, AccessLevel]
    menus: list[MenuOut]
    impersonation: ImpersonationOut = Field(default_factory=ImpersonationOut)
