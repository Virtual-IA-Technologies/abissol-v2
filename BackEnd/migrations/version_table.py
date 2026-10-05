from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection


VERSION_NUM_LENGTH = 128


def ensure_version_table_capacity(connection: Connection) -> None:
    """Create or widen Alembic's version table before applying revisions."""
    inspector = sa.inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        metadata = sa.MetaData()
        sa.Table(
            "alembic_version",
            metadata,
            sa.Column(
                "version_num",
                sa.String(VERSION_NUM_LENGTH),
                nullable=False,
                primary_key=True,
            ),
        ).create(connection, checkfirst=True)
        return

    column = next(
        (
            item
            for item in inspector.get_columns("alembic_version")
            if item["name"] == "version_num"
        ),
        None,
    )
    current_length = getattr(column["type"], "length", None) if column else None
    if current_length is None or current_length >= VERSION_NUM_LENGTH:
        return

    dialect = connection.dialect.name
    if dialect in {"mysql", "mariadb"}:
        connection.exec_driver_sql(
            f"ALTER TABLE alembic_version MODIFY COLUMN "
            f"version_num VARCHAR({VERSION_NUM_LENGTH}) NOT NULL"
        )
    elif dialect == "postgresql":
        connection.exec_driver_sql(
            f"ALTER TABLE alembic_version ALTER COLUMN "
            f"version_num TYPE VARCHAR({VERSION_NUM_LENGTH})"
        )
    # SQLite does not enforce VARCHAR length; no rebuild is necessary.
