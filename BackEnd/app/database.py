from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


# ============================================================
# CARGAR VARIABLES DE ENTORNO
# ============================================================

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from .config import get_settings


def obtener_variable(nombre: str, valor_defecto: str | None = None) -> str:
    """
    Obtiene una variable del archivo .env.

    Lanza un error claro si la variable obligatoria no existe.
    """

    valor = os.getenv(nombre, valor_defecto)

    if valor is None:
        raise RuntimeError(
            f"No se encontró la variable de entorno obligatoria: {nombre}"
        )

    return valor


# ============================================================
# BASE DE DATOS PRINCIPAL DEL SISTEMA
# ============================================================

settings = get_settings()
DB_USER = settings.db_user
DB_PASSWORD = settings.db_password
DB_HOST = settings.db_host
DB_PORT = settings.db_port
DB_NAME = settings.db_name

# Escapar usuario y contraseña por si contienen caracteres especiales
DB_USER_URL = quote_plus(DB_USER)
DB_PASSWORD_URL = quote_plus(DB_PASSWORD)

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER_URL}:{DB_PASSWORD_URL}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
    pool_size=10,
    max_overflow=20,
)


@event.listens_for(engine, "connect")
def configure_database_connection(dbapi_connection, _connection_record):
    """Hace que MariaDB rechace datos inválidos en lugar de corregirlos silenciosamente."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(
            "SET SESSION sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,"
            "NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION'"
        )
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("SET SESSION time_zone='+00:00'")
    finally:
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """
    Dependencia de FastAPI para la base principal.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
