
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from ..utils.time import utc_now

from ..database import Base


class DeviceSession(Base):
    """Sesión persistente y revocable. El token original nunca se almacena."""

    __tablename__ = "device_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    persistent = Column(Boolean, nullable=False, default=True)
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    last_used_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    revoked_reason = Column(String(40), nullable=True)
