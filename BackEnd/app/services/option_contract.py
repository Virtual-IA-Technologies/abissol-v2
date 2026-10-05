"""Contrato mínimo compartido por opciones con registros.

Une la unidad Wolverine y la auditoría funcional. Los servicios conservan sus
validaciones de dominio; este objeto evita que una ruta nueva olvide seguridad o
snapshots al ensamblar sus dependencias.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Request
from sqlalchemy.orm import Session

from ..models.user import Usuario
from ..routes.audit import audit_change
from .access_control import require_access


AccessLevel = Literal["lector", "editor", "gestor"]


@dataclass(frozen=True, slots=True)
class StandardOptionContract:
    slug: str
    module: str
    entity: str

    def require(self, level: AccessLevel = "lector"):
        """Dependencia FastAPI que vuelve a validar el nivel Wolverine."""
        return require_access(self.slug, level)

    def audit(
        self,
        db: Session,
        request: Request | None,
        user: Usuario,
        entity_id: str | int,
        *,
        before: Any = None,
        after: Any = None,
        detail: str | None = None,
        action_override: str | None = None,
    ) -> None:
        """Registra el cambio en la misma transacción con snapshots completos."""
        if before is None and after is None:
            raise ValueError("La auditoría funcional requiere un snapshot anterior o posterior")
        audit_change(
            db,
            request,
            user,
            self.entity,
            entity_id,
            before=before,
            after=after,
            module=self.module,
            detail=detail,
            action_override=action_override,
        )


def standard_option(slug: str, *, module: str, entity: str) -> StandardOptionContract:
    if not slug.strip() or not module.strip() or not entity.strip():
        raise ValueError("slug, module y entity son obligatorios")
    return StandardOptionContract(slug=slug.strip(), module=module.strip(), entity=entity.strip())
