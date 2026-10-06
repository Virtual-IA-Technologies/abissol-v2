"""Trazabilidad privada de la importación. Nunca serializar payload_encrypted en APIs."""
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from ..database import Base
from ..utils.time import utc_now


class LegacyRecord(Base):
    __tablename__ = 'legacy_abissol_records'
    __table_args__ = (UniqueConstraint('source_table', 'source_key', name='uq_legacy_record'),)
    id = Column(Integer, primary_key=True)
    source_table = Column(String(80), nullable=False)
    source_key = Column(String(120), nullable=False)
    target_id = Column(Integer)
    checksum = Column(String(64), nullable=False)
    payload_encrypted = Column(Text().with_variant(LONGTEXT(), 'mysql'), nullable=False)
    imported_at = Column(DateTime, nullable=False, default=utc_now)


class LegacyFile(Base):
    __tablename__ = 'legacy_abissol_files'
    id = Column(Integer, primary_key=True)
    path_hash = Column(String(64), unique=True, nullable=False)
    storage_key = Column(String(80), nullable=False)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    size = Column(Integer, nullable=False)


class MedicalBillingConfiguration(Base):
    __tablename__ = 'medical_billing_configuration'
    id = Column(Integer, primary_key=True)
    # Incluye claves SOL y certificado; acceso exclusivamente mediante lista blanca.
    payload_encrypted = Column(Text().with_variant(LONGTEXT(), 'mysql'), nullable=False)
