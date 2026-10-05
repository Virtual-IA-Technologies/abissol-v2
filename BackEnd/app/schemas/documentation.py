from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ArticleWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    titulo: str = Field(min_length=1, max_length=180)
    resumen: str = Field(default="", max_length=500)
    categoria: str = Field(default="General", min_length=1, max_length=100)
    audiencia: Literal["general", "tecnica", "interna"] = "general"
    estado: Literal["borrador", "publicado", "archivado"] = "borrador"
    contenido: str = Field(default="", max_length=200_000)
    motivo: str = Field(min_length=3, max_length=500)
    version: int | None = Field(default=None, ge=1)


class CommentAnchor(BaseModel):
    inicio: int = Field(ge=0, le=400_000)
    fin: int = Field(gt=0, le=400_000)

    @model_validator(mode="after")
    def valid_range(self):
        if self.fin <= self.inicio or self.fin - self.inicio > 4000:
            raise ValueError("Rango de cita inválido")
        return self


class CommentWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    contenido: str = Field(min_length=1, max_length=5000)
    cita: str = Field(default="", max_length=2000)
    ancla: CommentAnchor | None = None
    version_articulo: int = Field(ge=1)
    adjuntos: list[int] = Field(default_factory=list, max_length=5)


class RestoreWrite(BaseModel):
    version: int = Field(ge=1)
    motivo: str = Field(min_length=3, max_length=500)
