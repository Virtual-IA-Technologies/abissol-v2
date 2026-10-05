from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DocumentLookupRequest(BaseModel):
    option_slug: str = Field(min_length=2, max_length=120)
    document_type: Literal["dni", "ruc"]
    document_number: str

    @field_validator("document_number")
    @classmethod
    def validate_document(cls, value: str, info):
        normalized = "".join(character for character in value if character.isdigit())
        expected = 8 if info.data.get("document_type") == "dni" else 11
        if len(normalized) != expected:
            raise ValueError(f"El documento debe tener {expected} dígitos")
        return normalized


class DocumentLookupResponse(BaseModel):
    document_type: Literal["dni", "ruc"]
    document_number: str
    full_name: str | None = None
    business_name: str | None = None
    first_names: str | None = None
    paternal_surname: str | None = None
    maternal_surname: str | None = None
    status: str | None = None
    condition: str | None = None
    address: str | None = None
    ubigeo: str | None = None


class CatalogOption(BaseModel):
    value: str
    label: str
