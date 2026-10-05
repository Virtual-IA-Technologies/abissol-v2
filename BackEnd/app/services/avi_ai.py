from __future__ import annotations

import logging
import json
import os
import re
import time
from typing import Any

import httpx

from ..schemas.settings import (
    AviAISettings, AviProviderStatus,
)

logger = logging.getLogger("abissol.avi")

PROVIDER_ENV = {
    "gemini": ("AVI_GEMINI_API_KEY", "GEMINI_API_KEY"),
    "groq": ("AVI_GROQ_API_KEY", "GROQ_API_KEY"),
    "mistral": ("AVI_MISTRAL_API_KEY", "MISTRAL_API_KEY"),
}
_provider_failures: dict[str, tuple[int, float]] = {}

# Patrón básico de inyección de prompt; no se busca exhaustividad sino reducir ruido obvio.
_INJECTION_PATTERN = re.compile(
    r"(?:ignore|forget|disregard|override|system|assistant|instruccion|sistema)\s+"
    r"(?:previous|above|all|prior|instructions|instrucciones)",
    re.IGNORECASE,
)


def _api_key(provider: str) -> str:
    specific, standard = PROVIDER_ENV[provider]
    return (os.getenv(specific) or os.getenv(standard) or "").strip()


def _model(settings: AviAISettings, provider: str) -> str:
    return getattr(settings, f"{provider}_model")


def _sanitize(text: str, max_length: int = 2000) -> str:
    """Colapsa espacios y aplica un filtro básico de inyección de prompt."""
    text = " ".join(text.split())[:max_length]
    return _INJECTION_PATTERN.sub("[omitido]", text)


def provider_status(settings: AviAISettings) -> list[AviProviderStatus]:
    return [AviProviderStatus(
        provider=provider,
        configured=bool(_api_key(provider)),
        model=_model(settings, provider),
    ) for provider in settings.providers]


def is_available(settings: AviAISettings) -> bool:
    return settings.enabled and settings.external_ai_consent and any(item.configured for item in provider_status(settings))


def reset_provider_health() -> None:
    _provider_failures.clear()


def _provider_available(provider: str) -> bool:
    _, unavailable_until = _provider_failures.get(provider, (0, 0))
    return time.monotonic() >= unavailable_until


def _mark_failure(provider: str) -> None:
    failures, _ = _provider_failures.get(provider, (0, 0))
    cooldown = min(300, 15 * (2 ** min(failures, 4)))
    _provider_failures[provider] = (failures + 1, time.monotonic() + cooldown)


async def interpret_question(question, configuration):
    """Consentimiento de conversación; solo pregunta, nunca filas ni historial."""
    settings = configuration.ai
    if not is_available(settings):
        return None
    prompt = ('Interpreta la pregunta de plataforma. Devuelve SOLO JSON con query '
              '(pregunta de máximo 300 caracteres) y clarification (pregunta breve o null). '
              'Dominios disponibles: documentos, manuales, avisos y navegación. '
              'Conserva nombres y fechas; no inventes datos ni produzcas SQL o comandos.')
    for provider in settings.providers:
        key = _api_key(provider)
        if not key or not _provider_available(provider):
            continue
        try:
            messages = [{'role': 'user', 'content': _sanitize(question, 1000)}]
            model = _model(settings, provider)
            bounded = settings.model_copy(update={'timeout_seconds': min(settings.timeout_seconds, 12), 'max_output_tokens': min(settings.max_output_tokens, 500)})
            if provider == 'gemini':
                output = await _request_gemini(model, key, messages, bounded, prompt)
            else:
                output = await _request_openai_compatible(provider, model, key, messages, bounded, prompt)
            data = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', output.strip()))
            if not isinstance(data, dict) or set(data) - {'query', 'clarification'}:
                raise ValueError('Contrato no válido')
            if any(value is not None and (not isinstance(value, str) or len(value) > 300) for value in data.values()):
                raise ValueError('Texto no válido')
            query = data.get('query') or ''
            if re.search(r'\b(sql|select|insert|delete|update|drop|https?|crear|eliminar|anular|emitir|modificar)\b', query, re.I):
                raise ValueError('Acción no permitida')
            _provider_failures.pop(provider, None)
            return {'query': query, 'clarification': data.get('clarification')}
        except Exception as exc:
            _mark_failure(provider)
            logger.warning('AVI interpreter %s failed: %s', provider, type(exc).__name__)
    return None


async def _request_gemini(model: str, key: str, messages: list[dict[str, str]], settings: AviAISettings, system_prompt: str) -> str:
    contents = [{
        "role": "model" if item["role"] == "assistant" else "user",
        "parts": [{"text": item["content"]}],
    } for item in messages]
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": settings.max_output_tokens},
    }
    async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key}, json=payload,
        )
        response.raise_for_status()
    data = response.json()
    return "".join(
        part.get("text", "")
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    ).strip()


async def _request_openai_compatible(
    provider: str, model: str, key: str, messages: list[dict[str, str]], settings: AviAISettings, system_prompt: str
) -> str:
    url = {
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "mistral": "https://api.mistral.ai/v1/chat/completions",
    }[provider]
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": 0.2,
    }
    payload["max_completion_tokens" if provider == "groq" else "max_tokens"] = settings.max_output_tokens
    async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload)
        response.raise_for_status()
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content or "").strip()
