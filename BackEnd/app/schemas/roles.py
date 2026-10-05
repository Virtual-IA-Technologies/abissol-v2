from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleSummary(BaseModel):
    id: int
    nombre: str
    prioridad: int
    es_superusuario: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RoleWrite(BaseModel):
    nombre: str = Field(min_length=2, max_length=50)
    prioridad: int = Field(default=100, ge=0, le=9999)
    es_superusuario: bool = False
    is_active: bool = True
    is_default: bool = False

    @field_validator("nombre")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class RoleOut(RoleSummary):
    is_default: bool
    user_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=50)
    prioridad: int | None = Field(default=None, ge=0, le=9999)
    es_superusuario: bool | None = None
    is_active: bool | None = None
    is_default: bool | None = None

    @field_validator("nombre")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None
