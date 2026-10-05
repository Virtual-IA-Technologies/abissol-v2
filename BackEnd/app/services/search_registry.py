from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..models.user import Usuario
from ..schemas.search import GlobalSearchResult


SearchLoader = Callable[
    [Session, Usuario, list[str], str],
    list[GlobalSearchResult],
]


@dataclass(frozen=True)
class SearchProvider:
    name: str
    slug: str | None
    load: SearchLoader


_providers: dict[str, SearchProvider] = {}


def register_search_provider(slug: str | None, *, name: str | None = None):
    """Register a module search without editing the global search endpoint."""

    def decorator(loader: SearchLoader) -> SearchLoader:
        provider_name = name or f"{loader.__module__}.{loader.__name__}"
        _providers[provider_name] = SearchProvider(
            name=provider_name,
            slug=slug,
            load=loader,
        )
        return loader

    return decorator


def get_search_providers() -> tuple[SearchProvider, ...]:
    return tuple(_providers.values())


def normalize_search_text(value: object) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )


def contains_all_search_terms(values: list[object], terms: list[str]) -> bool:
    text = normalize_search_text(" ".join(str(value or "") for value in values))
    return all(term in text for term in terms)


def database_search_filter(columns, terms: list[str]):
    return and_(*[
        or_(*[
            func.lower(column).contains(term, autoescape=True)
            for column in columns
        ])
        for term in terms
    ])


def search_result_url(path: str, query: str, **extra: object) -> str:
    return f"{path}?{urlencode({'buscar': query, **extra})}"
