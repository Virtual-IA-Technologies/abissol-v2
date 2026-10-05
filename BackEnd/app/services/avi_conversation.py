from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..schemas.settings import (
    AviCapabilityCandidate,
    AviConfiguration,
    AviContextResult,
    AviInterpretation,
    AviInterpretRequest,
)


@dataclass(frozen=True)
class Capability:
    name: str
    display_name: str
    description: str
    examples: tuple[str, ...]
    setting: str
    permission: str | None = None


CAPABILITIES = (
    Capability(
        "notifications", "Revisar avisos",
        "Consulta notificaciones, avisos y asuntos pendientes del usuario.",
        ("mis notificaciones", "que avisos tengo", "que tengo pendiente", "que se me esta quedando atras", "algo nuevo"),
        "notifications", "notificaciones",
    ),
    Capability(
        "search_documents", "Buscar documentos",
        "Busca archivos y documentos autorizados dentro de ABISSOL.",
        ("documentos", "buscar documentos", "mis archivos", "encuentra el documento", "revisar un archivo", "documentos de"),
        "document_management", "documentos",
    ),
    Capability(
        "search_documentation", "Consultar ayuda",
        "Busca manuales, guias y documentacion de uso de ABISSOL.",
        ("manual", "como hago", "ayudame a", "manual de", "guia para", "como se usa"),
        "documentation", "documentacion",
    ),
    Capability(
        "navigate", "Buscar opciones y registros",
        "Busca opciones, pantallas y registros autorizados para orientar al usuario.",
        ("opciones disponibles", "donde esta", "ir a", "abre", "busca", "encuentra", "muestrame"),
        "navigation",
    ),
)

_ORDINALS = {
    "primero": 0, "primera": 0, "1": 0,
    "segundo": 1, "segunda": 1, "2": 1,
    "tercero": 2, "tercera": 2, "3": 2,
    "cuarto": 3, "cuarta": 3, "4": 3,
    "quinto": 4, "quinta": 4, "5": 4,
}
_READ_ONLY_ACTION = re.compile(
    r"\b(crea|crear|elimina|eliminar|borra|borrar|modifica|modificar|cambia|cambiar|"
    r"mueve|mover|comparte|compartir|envia|enviar|llama|llamar)\b"
)
_CONTEXT_REFERENCE = re.compile(
    r"\b(ese|esa|este|esta|el mismo|la misma|el anterior|la anterior|el ultimo|la ultima|"
    r"primero|primera|segundo|segunda|tercero|tercera|cuarto|cuarta|quinto|quinta)\b"
)
_DOCUMENT_REFERENCE = re.compile(r"\b(sus|ese|esa|aquellos|aquellas)\s+(documentos|archivos)\b")


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _tokens(text: str) -> set[str]:
    return {token for token in normalize(text).split() if len(token) > 2}


def enabled_capabilities(configuration: AviConfiguration, permissions: set[str]) -> list[Capability]:
    result = []
    for capability in CAPABILITIES:
        if not getattr(configuration.capabilities, capability.setting):
            continue
        if capability.permission and capability.permission not in permissions:
            continue
        result.append(capability)
    return result


def _score(question: str, capability: Capability) -> tuple[float, bool]:
    normalized = normalize(question)
    question_tokens = _tokens(question)
    best = 0.0
    exact = False
    for example in capability.examples:
        normalized_example = normalize(example)
        if normalized == normalized_example or normalized_example in normalized:
            best = max(best, 0.97 if normalized == normalized_example else 0.92)
            exact = True
            continue
        example_tokens = _tokens(example)
        overlap = len(question_tokens & example_tokens) / max(1, len(example_tokens))
        sequence = SequenceMatcher(None, normalized, normalized_example).ratio()
        best = max(best, min(0.89, overlap * 0.72 + sequence * 0.28))
    return round(best, 4), exact


def _context_result(question: str, results: list[AviContextResult]) -> AviContextResult | None:
    if not results:
        return None
    normalized = normalize(question)
    if "ultimo" in normalized or "ultima" in normalized:
        return results[-1]
    for word, index in _ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", normalized) and index < len(results):
            return results[index]
    if re.search(r"\b(ese|esa|este|esta|el mismo|la misma|el anterior|la anterior)\b", normalized):
        return results[-1] if len(results) == 1 else None
    return None


def fallback_message(reason: str, capability: str | None = None) -> str:
    if reason == "MISSING_ENTITY":
        return "Claro. ¿De qué persona, opción o documento quieres que haga la búsqueda?"
    if reason == "MULTIPLE_MATCHES":
        return "Encontré varias posibilidades. Indícame cuál deseas revisar o elige una de la lista."
    if reason == "UNSUPPORTED_CAPABILITY":
        return (
            "Todavía no puedo realizar cambios ni iniciar comunicaciones desde la conversación. "
            "Sí puedo ayudarte a encontrar la opción correcta y guiarte paso a paso."
        )
    if reason == "PERMISSION_DENIED":
        return "No tienes acceso a esa información. Puedo ayudarte con otra opción que sí tengas autorizada."
    if reason == "PROVIDER_FAILURE":
        return "No pude completar la interpretación inteligente en este momento. Podemos intentarlo con otras palabras."
    if reason == "NO_RESULTS" and capability == "search_documents":
        return "No encontré documentos autorizados con ese criterio. Prueba con el nombre del archivo o una palabra más específica."
    if reason == "NO_RESULTS" and capability == "search_documentation":
        return "No encontré una guía con ese criterio. Dime qué procedimiento necesitas realizar y lo buscamos de otra forma."
    if reason == "NO_RESULTS":
        return "No encontré coincidencias autorizadas. Prueba con un nombre, módulo o dato más específico."
    return "No estoy segura de qué deseas revisar. Cuéntamelo con otras palabras o menciona el módulo relacionado."


def route_message(
    payload: AviInterpretRequest,
    configuration: AviConfiguration,
    permissions: set[str],
) -> AviInterpretation:
    question = normalize(payload.question)

    # Una aclaración pendiente se completa antes de volver a clasificar el mensaje.
    if payload.history:
        previous = payload.history[-1]
        if previous.role == "assistant" and previous.fallback_reason in {"MISSING_ENTITY", "MISSING_PARAMETER"}:
            capability = previous.capability or "navigate"
            return AviInterpretation(
                capability=capability, source="context", routing_confidence=0.94,
                entity_confidence=0.9, parameter_confidence=0.88, context_confidence=0.96,
                parameters={"search_query": payload.question.strip()},
                no_results_message=fallback_message("NO_RESULTS", capability),
            )

    # La politica de solo lectura prevalece incluso cuando el texto contiene una referencia contextual.
    if _READ_ONLY_ACTION.search(question):
        return AviInterpretation(
            source="fallback", routing_confidence=0.98, requires_clarification=False,
            fallback_reason="UNSUPPORTED_CAPABILITY",
            message=fallback_message("UNSUPPORTED_CAPABILITY"),
        )

    if _CONTEXT_REFERENCE.search(question):
        selected = _context_result(question, payload.context_results)
        if selected:
            return AviInterpretation(
                capability="open_result", source="context", routing_confidence=1,
                entity_confidence=1, parameter_confidence=1, context_confidence=1,
                selected_result=selected,
                message=f'Entendido. Te muestro “{selected.title}”.',
            )
        return AviInterpretation(
            source="fallback", context_confidence=0.25, requires_clarification=True,
            fallback_reason="CONTEXT_CONFLICT",
            message="No tengo una lista anterior que permita identificar esa referencia. ¿Cuál resultado quieres revisar?",
        )

    if _DOCUMENT_REFERENCE.search(question) and not payload.context_results:
        return AviInterpretation(
            capability="search_documents", source="fallback", routing_confidence=0.86,
            entity_confidence=0.15, requires_clarification=True, fallback_reason="MISSING_ENTITY",
            message=fallback_message("MISSING_ENTITY"),
        )

    capabilities = enabled_capabilities(configuration, permissions)
    ranked = []
    exact_matches: set[str] = set()
    for capability in capabilities:
        score, exact = _score(payload.question, capability)
        ranked.append((score, capability))
        if exact:
            exact_matches.add(capability.name)
    ranked.sort(key=lambda item: item[0], reverse=True)
    candidates = [
        AviCapabilityCandidate(capability=item.name, display_name=item.display_name, score=score)
        for score, item in ranked[:3] if score >= 0.2
    ]
    if ranked and ranked[0][0] >= 0.58:
        score, capability = ranked[0]
        source = "exact" if capability.name in exact_matches else "semantic"
        return AviInterpretation(
            capability=capability.name, source=source, routing_confidence=score,
            entity_confidence=0.8, parameter_confidence=0.85, context_confidence=0.5,
            parameters={"search_query": payload.question.strip()}, candidates=candidates,
            no_results_message=fallback_message("NO_RESULTS", capability.name),
        )
    return AviInterpretation(
        source="fallback", routing_confidence=ranked[0][0] if ranked else 0,
        candidates=candidates, requires_clarification=True, fallback_reason="LOW_CONFIDENCE",
        message=fallback_message("LOW_CONFIDENCE"),
    )


def validate_llm_interpretation(
    result: AviInterpretation,
    candidates: list[AviCapabilityCandidate],
) -> AviInterpretation | None:
    allowed = {candidate.capability for candidate in candidates}
    if not result.capability or result.capability not in allowed:
        return None
    result.source = "llm"
    result.candidates = candidates
    result.routing_confidence = min(result.routing_confidence, 0.89)
    result.no_results_message = fallback_message("NO_RESULTS", result.capability)
    return result
