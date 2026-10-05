from __future__ import annotations

from typing import Sequence

from .provider import AIMessage, AIProvider, AIResult


class AIService:
    def __init__(self, provider: AIProvider | None = None):
        self._provider = provider

    @property
    def configured(self) -> bool:
        return self._provider is not None

    def generate(self, messages: Sequence[AIMessage], *, purpose: str) -> AIResult:
        if self._provider is None:
            raise RuntimeError("No hay un proveedor de IA configurado")
        return self._provider.generate(messages, purpose=purpose)


_service = AIService()


def get_ai_service() -> AIService:
    return _service
