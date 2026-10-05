from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from ..database import Base
from ..utils.time import utc_now


class CloudSetting(Base):
    __tablename__ = 'document_cloud_settings'
    id = Column(Integer, primary_key=True)
    client_id = Column(String(250), nullable=False)
    secret = Column(Text, nullable=False)
    redirect_uri = Column(String(500), nullable=False)
    frontend_origin = Column(String(250), nullable=False)


class CloudAuth(Base):
    __tablename__ = 'document_cloud_auth'
    state_hash = Column(String(64), primary_key=True)
    owner_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    verifier = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class CloudAccount(Base):
    __tablename__ = 'document_cloud_accounts'
    __table_args__ = (UniqueConstraint('owner_id', 'provider', 'remote_id', name='uq_cloud_account'),)
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    provider = Column(String(20), nullable=False, default='google')
    remote_id = Column(String(160), nullable=False)
    label = Column(String(180), nullable=False)
    email = Column(String(250), nullable=False)
    credentials = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    lease_token = Column(String(40))
    lease_until = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class CloudFolder(Base):
    __tablename__ = 'document_cloud_folders'
    __table_args__ = (UniqueConstraint('account_id', 'remote_id', name='uq_cloud_folder'),)
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('document_cloud_accounts.id'), nullable=False, index=True)
    remote_id = Column(String(160), nullable=False)
    name = Column(String(180), nullable=False)
    folder_id = Column(Integer, ForeignKey('document_folders.id'), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    cursor = Column(Text)
    scan_page = Column(Text)
    scanning = Column(Boolean, nullable=False, default=True)
    next_run = Column(DateTime, nullable=False, default=utc_now, index=True)
    last_run = Column(DateTime)
    status = Column(String(30), nullable=False, default='pending')
    message = Column(String(500), nullable=False, default='')


class CloudSource(Base):
    __tablename__ = 'document_cloud_sources'
    __table_args__ = (UniqueConstraint('account_id', 'remote_id', name='uq_cloud_source'),)
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('document_cloud_accounts.id'), nullable=False, index=True)
    remote_id = Column(String(160), nullable=False)
    name = Column(String(180), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), index=True)
    remote_version = Column(String(100))
    local_version = Column(Integer)
    status = Column(String(30), nullable=False, default='pending')
    message = Column(String(500), nullable=False, default='')
    updated_at = Column(DateTime, nullable=False, default=utc_now)
