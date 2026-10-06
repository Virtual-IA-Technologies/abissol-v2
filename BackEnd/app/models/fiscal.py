from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from ..database import Base
from ..utils.time import utc_now


class FiscalJob(Base):
    __tablename__ = 'medical_fiscal_jobs'
    __table_args__ = (UniqueConstraint('environment', 'series', 'number', name='uq_fiscal_number'),)
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('medical_invoices.id'), unique=True, nullable=False)
    environment = Column(String(20), nullable=False)
    series = Column(String(4), nullable=False)
    number = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False, default='queued', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    sent_at = Column(DateTime)
    next_attempt_at = Column(DateTime, nullable=False, default=utc_now)
    error = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
