from typing import Literal

from pydantic import BaseModel


class GlobalSearchResult(BaseModel):
    id: str
    source: str
    kind: Literal["option", "record"]
    title: str
    subtitle: str
    url: str


class GlobalSearchResponse(BaseModel):
    query: str
    results: list[GlobalSearchResult]
    truncated: bool = False
