from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class AIMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AIResult:
    content: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIProvider(Protocol):
    """Contrato mínimo para poder cambiar de proveedor sin afectar ABISSOL."""

    def generate(self, messages: Sequence[AIMessage], *, purpose: str) -> AIResult:
        ...
