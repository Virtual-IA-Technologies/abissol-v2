"""MariaDB DATETIME almacena UTC sin zona; los contratos HTTP declaran UTC."""
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utc_iso(value: datetime | None) -> str | None:
    """Serializa instantes internos como UTC explícito, incluso si MariaDB quitó la zona."""
    if value is None:
        return None
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat()
