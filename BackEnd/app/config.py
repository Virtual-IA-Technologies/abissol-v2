from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
    return value


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_version: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    secret_key: str
    cors_origins: tuple[str, ...]
    device_session_days: int
    auto_create_schema: bool
    expected_db_name: str
    frontend_url: str
    password_reset_minutes: int
    apiperu_base_url: str
    apiperu_api_token: str
    apiperu_timeout_seconds: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    secret_key = _required("SECRET_KEY")
    if environment == "production" and len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY debe tener al menos 32 caracteres en produccion")

    db_name = _required("DB_NAME")
    expected_db_name = os.getenv(
        "EXPECTED_DB_NAME",
        "abissol_v2" if environment == "production" else "abissol_v2_local",
    ).strip()
    if db_name != expected_db_name:
        raise RuntimeError(
            f"Base de datos bloqueada: DB_NAME={db_name!r}; se esperaba {expected_db_name!r} "
            f"para APP_ENV={environment!r}"
        )

    return Settings(
        app_env=environment,
        app_version=os.getenv("APP_VERSION", "0.2.0").strip() or "0.2.0",
        db_host=os.getenv("DB_HOST", "127.0.0.1").strip(),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_name=db_name,
        db_user=_required("DB_USER"),
        db_password=os.getenv("DB_PASSWORD", ""),
        secret_key=secret_key,
        cors_origins=tuple(
            value.strip()
            for value in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5185,http://127.0.0.1:5185",
            ).split(",")
            if value.strip()
        ),
        device_session_days=int(os.getenv("DEVICE_SESSION_DAYS", "365")),
        auto_create_schema=_boolean("AUTO_CREATE_SCHEMA", False),
        expected_db_name=expected_db_name,
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5185").strip().rstrip("/"),
        password_reset_minutes=int(os.getenv("PASSWORD_RESET_MINUTES", "30")),
        apiperu_base_url=os.getenv("APIPERU_BASE_URL", "https://api.apiperu.dev").strip().rstrip("/"),
        apiperu_api_token=os.getenv("APIPERU_API_TOKEN", "").strip(),
        apiperu_timeout_seconds=float(os.getenv("APIPERU_TIMEOUT_SECONDS", "8")),
    )
