from pydantic import BaseModel, Field
from .settings import AviContextResult


class AviAgentResponse(BaseModel):
    message: str
    source: str = 'AVI · datos autorizados de ABISSOL'
    capability: str | None = None
    results: list[AviContextResult] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    truncated: bool = False
    navigate_to: str | None = None
