from __future__ import annotations

from dataclasses import dataclass

import httpx

from ..config import get_settings


class ApiPeruUnavailable(RuntimeError):
    pass


class ApiPeruNotFound(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiPeruResult:
    payload: dict


def lookup_document(document_type: str, document_number: str) -> ApiPeruResult:
    settings = get_settings()
    if not settings.apiperu_api_token:
        raise ApiPeruUnavailable("La consulta DNI/RUC todavía no está configurada")
    try:
        response = httpx.post(
            f"{settings.apiperu_base_url}/{document_type}",
            headers={"Authorization": f"Bearer {settings.apiperu_api_token}"},
            json={document_type: document_number},
            timeout=settings.apiperu_timeout_seconds,
        )
    except httpx.RequestError as exc:
        raise ApiPeruUnavailable("El proveedor de documentos no está disponible") from exc
    if response.status_code == 404:
        raise ApiPeruNotFound("No se encontró el documento")
    if response.status_code >= 500:
        raise ApiPeruUnavailable("El proveedor de documentos no está disponible")
    if response.status_code >= 400:
        raise ApiPeruUnavailable("El proveedor rechazó la consulta")
    try:
        body = response.json()
    except ValueError as exc:
        raise ApiPeruUnavailable("El proveedor devolvió una respuesta inválida") from exc
    if not body.get("success") or not isinstance(body.get("data"), dict):
        if body.get("code") == "document_not_found":
            raise ApiPeruNotFound("No se encontró el documento")
        raise ApiPeruUnavailable("No fue posible completar la consulta")
    return ApiPeruResult(payload=body["data"])


def public_document_result(document_type: str, document_number: str, data: dict) -> dict:
    def first(*keys: str):
        return next((data.get(key) for key in keys if data.get(key) not in (None, "")), None)

    return {
        "document_type": document_type,
        "document_number": document_number,
        "full_name": first("nombre_completo", "nombreCompleto", "nombres_completos"),
        "business_name": first("razon_social", "razonSocial", "nombre_o_razon_social"),
        "first_names": first("nombres"),
        "paternal_surname": first("apellido_paterno", "apellidoPaterno"),
        "maternal_surname": first("apellido_materno", "apellidoMaterno"),
        "status": first("estado"),
        "condition": first("condicion"),
        "address": first("direccion", "direccion_completa"),
        "ubigeo": first("ubigeo", "ubigeo_sunat"),
    }
