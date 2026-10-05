from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CalendarStatus = Literal["pendiente", "confirmado", "en_progreso", "completado", "cancelado"]
CalendarPriority = Literal["baja", "media", "alta", "urgente"]
CalendarVisibility = Literal["personal", "equipo"]
ReminderChannel = Literal["interno", "correo"]


class CalendarReminderWrite(BaseModel):
    minutos_antes: int = Field(ge=0, le=525600)
    canal: ReminderChannel = "interno"


class CalendarLabelWrite(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#2563eb", pattern=r"^#[0-9A-Fa-f]{6}$")


class CalendarEventWrite(BaseModel):
    titulo: str = Field(min_length=1, max_length=160)
    descripcion: str | None = Field(default=None, max_length=5000)
    inicio: datetime
    fin: datetime
    todo_el_dia: bool = False
    estado: CalendarStatus = "pendiente"
    prioridad: CalendarPriority = "media"
    visibilidad: CalendarVisibility = "equipo"
    ubicacion: str | None = Field(default=None, max_length=200)
    asignado_ids: list[int] = Field(default_factory=list)
    etiqueta_ids: list[int] = Field(default_factory=list)
    recordatorios: list[CalendarReminderWrite] = Field(default_factory=list, max_length=8)
    origen_modulo: str | None = Field(default=None, max_length=80)
    origen_tipo: str | None = Field(default=None, max_length=80)
    origen_id: str | None = Field(default=None, max_length=80)
    origen_url: str | None = Field(default=None, max_length=255)

    @field_validator("inicio", "fin")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value

    @field_validator("asignado_ids", "etiqueta_ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("No se permiten elementos repetidos")
        return value

    @field_validator("origen_url")
    @classmethod
    def internal_origin_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("/"):
            raise ValueError("La ruta vinculada debe ser interna")
        return value

    @model_validator(mode="after")
    def validate_period(self):
        if self.fin <= self.inicio:
            raise ValueError("La fecha final debe ser posterior a la inicial")
        reminder_keys = {(item.minutos_antes, item.canal) for item in self.recordatorios}
        if len(reminder_keys) != len(self.recordatorios):
            raise ValueError("No se permiten recordatorios repetidos")
        return self


class CalendarEventUpdate(BaseModel):
    version: int = Field(ge=1)
    titulo: str | None = Field(default=None, min_length=1, max_length=160)
    descripcion: str | None = Field(default=None, max_length=5000)
    inicio: datetime | None = None
    fin: datetime | None = None
    todo_el_dia: bool | None = None
    estado: CalendarStatus | None = None
    prioridad: CalendarPriority | None = None
    visibilidad: CalendarVisibility | None = None
    ubicacion: str | None = Field(default=None, max_length=200)
    asignado_ids: list[int] | None = None
    etiqueta_ids: list[int] | None = None
    recordatorios: list[CalendarReminderWrite] | None = Field(default=None, max_length=8)
    origen_modulo: str | None = Field(default=None, max_length=80)
    origen_tipo: str | None = Field(default=None, max_length=80)
    origen_id: str | None = Field(default=None, max_length=80)
    origen_url: str | None = Field(default=None, max_length=255)

    @field_validator("inicio", "fin")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC).replace(tzinfo=None) if value is not None and value.tzinfo is not None else value

    @field_validator("asignado_ids", "etiqueta_ids")
    @classmethod
    def unique_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("No se permiten elementos repetidos")
        return value

    @field_validator("origen_url")
    @classmethod
    def internal_origin_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("/"):
            raise ValueError("La ruta vinculada debe ser interna")
        return value

    @model_validator(mode="after")
    def unique_reminders(self):
        if self.recordatorios is not None:
            keys = {(item.minutos_antes, item.canal) for item in self.recordatorios}
            if len(keys) != len(self.recordatorios):
                raise ValueError("No se permiten recordatorios repetidos")
        return self


class CalendarLabelOut(BaseModel):
    id: int
    nombre: str
    color: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CalendarPersonOut(BaseModel):
    id: int
    nombre: str
    username: str


class CalendarReminderOut(BaseModel):
    id: int
    minutos_antes: int
    canal: ReminderChannel


class CalendarEventOut(BaseModel):
    id: int
    titulo: str
    descripcion: str | None
    inicio: str
    fin: str
    todo_el_dia: bool
    estado: CalendarStatus
    prioridad: CalendarPriority
    visibilidad: CalendarVisibility
    ubicacion: str | None
    propietario: CalendarPersonOut
    asignados: list[CalendarPersonOut]
    etiquetas: list[CalendarLabelOut]
    recordatorios: list[CalendarReminderOut]
    origen_modulo: str | None
    origen_tipo: str | None
    origen_id: str | None
    origen_url: str | None
    version: int
    created_at: str
    updated_at: str
