from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, JSON
from ..database import Base
from ..utils.time import utc_now


class DocumentTrashPolicy(Base):
    __tablename__ = 'document_trash_policies'
    owner_id = Column(Integer, ForeignKey('usuarios.id'), primary_key=True)
    days = Column(Integer, nullable=False, default=0)


class DocumentFileRemoval(Base):
    __tablename__ = 'document_file_removals'
    storage_key = Column(String(80), primary_key=True)


class DocumentFolder(Base):
    __tablename__ = 'document_folders'
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('document_folders.id'), index=True)
    owner_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    system_key = Column(String(180), unique=True)
    deleted_at = Column(DateTime, index=True)
    trash_batch = Column(String(32), index=True)


class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    folder_id = Column(Integer, ForeignKey('document_folders.id'), index=True)
    title = Column(String(180), nullable=False, index=True)
    description = Column(String(1000), nullable=False, default='')
    is_system = Column(Boolean, nullable=False, default=False, server_default='0', index=True)
    current_version = Column(Integer, nullable=False, default=1)
    revision = Column(Integer, nullable=False, default=1)
    deleted_at = Column(DateTime, index=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    trash_batch = Column(String(32), index=True)
    __mapper_args__ = {'version_id_col': revision}


class DocumentBinding(Base):
    __tablename__ = 'document_bindings'
    __table_args__ = (UniqueConstraint('source_type','source_id','artifact_key',name='uq_document_source_artifact'),)
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, unique=True)
    source_type = Column(String(40), nullable=False)
    source_id = Column(Integer, nullable=False)
    artifact_key = Column(String(80), nullable=False)


class DocumentVersion(Base):
    __tablename__ = 'document_versions'
    __table_args__ = (UniqueConstraint('document_id', 'number', name='uq_document_version'),)
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    author_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    filename = Column(String(180), nullable=False)
    storage_key = Column(String(80), nullable=False, unique=True)
    mime = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    reason = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    # Extraction and vector indexing are separate stages; never label an unindexed file ready.
    processing = Column(String(30), nullable=False, default='pending')
    text = Column(Text, nullable=True)


class DocumentTextChunk(Base):
    """Fragmento extraido e indexable; nunca contiene binarios ni amplia permisos."""

    __tablename__ = 'document_text_chunks'
    __table_args__ = (
        UniqueConstraint('version_id', 'position', name='uq_document_text_chunk'),
        Index('ft_document_text_chunks_content', 'content', mysql_prefix='FULLTEXT'),
    )
    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey('document_versions.id', ondelete='CASCADE'), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)


class DocumentShare(Base):
    __tablename__ = 'document_shares'
    __table_args__ = (UniqueConstraint('document_id', 'user_id', name='uq_document_share'),)
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class DocumentNotes(Base):
    __tablename__ = 'document_notes'
    version_id = Column(Integer, ForeignKey('document_versions.id'), primary_key=True)
    revision = Column(Integer, nullable=False, default=1)
    items = Column(JSON, nullable=False, default=list)
    author_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now)
    __mapper_args__ = {'version_id_col': revision}


class DocumentEditSession(Base):
    __tablename__ = 'document_edit_sessions'
    id = Column(String(32), primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    version_id = Column(Integer, ForeignKey('document_versions.id'), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    expected_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)
    saved_hash = Column(String(64))


class DocumentLink(Base):
    __tablename__ = 'document_links'
    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey('document_versions.id'), index=True)
    author_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    purpose = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime)
    storage_key = Column(String(80))
    filename = Column(String(180))
    mime = Column(String(100))
