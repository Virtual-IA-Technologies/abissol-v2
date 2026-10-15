from sqlalchemy import Column, DateTime, ForeignKey, Integer
from ..database import Base


class SupportChatPresence(Base):
    __tablename__ = 'support_chat_presence'
    device_session_id = Column(Integer, ForeignKey('device_sessions.id', ondelete='CASCADE'), primary_key=True)
    seen_at = Column(DateTime, nullable=False)
