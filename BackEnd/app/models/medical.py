"""Negocio ABISSOL; independiente de las tablas del sistema anterior."""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from ..database import Base
from ..utils.time import utc_now


class MedicalPlan(Base):
    __tablename__ = "medical_plans"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    prefix = Column(String(15), unique=True, nullable=False)
    counter = Column(Integer, nullable=False, default=0)
    price = Column(Numeric(12, 2), nullable=False)
    provider_cost = Column(Numeric(12, 2), nullable=False)
    seller_commission = Column(Numeric(12, 2), nullable=False)
    platform_fee = Column(Numeric(12, 2), nullable=False, default=0)
    meta_percent = Column(Numeric(5, 2), nullable=False, default=10)
    validity_days = Column(Integer, nullable=False, default=365)
    conditions_url = Column(String(500), nullable=False, default="")
    active = Column(Boolean, nullable=False, default=True)


class MedicalSource(Base):
    __tablename__ = "medical_sources"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class MedicalProfile(Base):
    __tablename__ = "medical_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False)
    source_id = Column(Integer, ForeignKey("medical_sources.id"), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("medical_profiles.id"))
    kind = Column(String(25), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class MedicalIssuance(Base):
    __tablename__ = "medical_issuances"
    __table_args__ = (UniqueConstraint("external_source", "external_reference", name="uq_medical_external"),)
    id = Column(Integer, primary_key=True)
    code = Column(String(40), unique=True, nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("medical_plans.id"), nullable=False)
    plan_name = Column(String(120), nullable=False)
    source_id = Column(Integer, ForeignKey("medical_sources.id"), nullable=False, index=True)
    emitter_id = Column(Integer, ForeignKey("medical_profiles.id"), nullable=False, index=True)
    responsible_id = Column(Integer, ForeignKey("medical_profiles.id"), nullable=False, index=True)
    document_type = Column(String(10), nullable=False)
    document_number = Column(String(20), nullable=False, index=True)
    customer = Column(String(180), nullable=False)
    email = Column(String(180), nullable=False, default="")
    phone = Column(String(25), nullable=False, default="")
    sale_date = Column(Date, nullable=False)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    provider_cost = Column(Numeric(12, 2), nullable=False)
    seller_commission = Column(Numeric(12, 2), nullable=False)
    platform_fee = Column(Numeric(12, 2), nullable=False)
    meta_commission = Column(Numeric(12, 2), nullable=False, default=0)
    conditions_url = Column(String(500), nullable=False, default="")
    status = Column(String(25), nullable=False, default="issued")
    payment_status = Column(String(30), nullable=False, default="pending")
    payment_method = Column(String(25), nullable=False)
    paid_amount = Column(Numeric(12, 2), nullable=False, default=0)
    cancellation_reason = Column(Text)
    external_source = Column(String(80))
    external_reference = Column(String(100))
    created_by = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class MedicalLiquidation(Base):
    __tablename__ = "medical_liquidations"
    id = Column(Integer, primary_key=True)
    kind = Column(String(20), nullable=False)
    responsible_id = Column(Integer, ForeignKey("medical_profiles.id"), nullable=False, index=True)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    sales_total = Column(Numeric(12, 2), nullable=False, default=0)
    commission_total = Column(Numeric(12, 2), nullable=False, default=0)
    deposit_required = Column(Numeric(12, 2), nullable=False, default=0)
    notes = Column(Text, nullable=False, default="")
    created_by = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class MedicalLiquidationItem(Base):
    __tablename__ = "medical_liquidation_items"
    id = Column(Integer, primary_key=True)
    liquidation_id = Column(Integer, ForeignKey("medical_liquidations.id"), nullable=False, index=True)
    issuance_id = Column(Integer, ForeignKey("medical_issuances.id"), nullable=False)
    active_key = Column(String(50), unique=True)
    sale = Column(Numeric(12, 2), nullable=False)
    commission = Column(Numeric(12, 2), nullable=False)
    deposit = Column(Numeric(12, 2), nullable=False)


class MedicalVoucher(Base):
    __tablename__ = "medical_vouchers"
    id = Column(Integer, primary_key=True)
    liquidation_id = Column(Integer, ForeignKey("medical_liquidations.id"), nullable=False, index=True)
    reference = Column(String(100), nullable=False)
    active_reference = Column(String(100), unique=True)
    amount = Column(Numeric(12, 2), nullable=False)
    paid_on = Column(Date, nullable=False)
    filename = Column(String(180), nullable=False)
    storage_key = Column(String(80), nullable=False)
    digest = Column(String(64), nullable=False)
    active_digest = Column(String(64), unique=True)
    active = Column(Boolean, nullable=False, default=True)


class MedicalInvoice(Base):
    __tablename__ = "medical_invoices"
    id = Column(Integer, primary_key=True)
    issuance_id = Column(Integer, ForeignKey("medical_issuances.id"), unique=True, nullable=False)
    document_type = Column(String(20), nullable=False)
    customer = Column(String(180), nullable=False)
    document_number = Column(String(20), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    sunat_status = Column(String(30), nullable=False, default="not_sent")
    created_by = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class MedicalDispatch(Base):
    __tablename__ = "medical_dispatches"
    id = Column(Integer, primary_key=True)
    issuance_id = Column(Integer, ForeignKey("medical_issuances.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    recipient = Column(String(180), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(String(250), nullable=False, default="")
    created_by = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
