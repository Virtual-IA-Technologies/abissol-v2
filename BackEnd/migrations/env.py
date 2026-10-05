from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.database import Base, SQLALCHEMY_DATABASE_URL
import app.models  # noqa: F401
from migrations.version_table import ensure_version_table_capacity

config = context.config
config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tablas heredadas vacías conservadas para no ejecutar una eliminación
# implícita durante una verificación o migración autogenerada. Wolverine usa
# access_grants; estas tablas no forman parte del modelo activo.
PRESERVED_LEGACY_TABLES = {"permisos", "rol_permission"}


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name in PRESERVED_LEGACY_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=SQLALCHEMY_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from app.database import engine

    with engine.begin() as connection:
        ensure_version_table_capacity(connection)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
