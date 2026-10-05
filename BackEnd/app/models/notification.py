from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, JSON

from ..database import Base
from ..utils.time import utc_now


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    source = Column(String(80), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="info", index=True)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    entity = Column(String(80), nullable=True)
    entity_id = Column(String(80), nullable=True)
    url = Column(String(255), nullable=True)
    dedupe_key = Column(String(190), nullable=True)
    read_at = Column(DateTime, nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    __table_args__ = (UniqueConstraint("usuario_id", "dedupe_key", name="uq_notification_recipient_dedupe"),)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(80), nullable=False)
    internal_enabled = Column(Boolean, nullable=False, default=True)
    email_enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    __table_args__ = (UniqueConstraint("usuario_id", "event_type", name="uq_notification_preference"),)


class NotificationRule(Base):
    __tablename__ = 'notification_rules'
    event_type = Column(String(80), primary_key=True)
    recipients = Column(JSON, nullable=False)
    channels = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class NotificationDelivery(Base):
    __tablename__ = 'notification_deliveries'
    id = Column(Integer, primary_key=True)
    notification_id = Column(Integer, ForeignKey('notifications.id'), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='queued', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(String(80))
    created_at = Column(DateTime, nullable=False, default=utc_now)
    finished_at = Column(DateTime)
    __table_args__ = (UniqueConstraint('notification_id', 'channel', name='uq_notification_delivery_channel'),)
