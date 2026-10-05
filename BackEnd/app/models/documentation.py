from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from ..database import Base
from ..utils.time import utc_now


def long_text():
    return Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb")


class DocArticle(Base):
    __tablename__ = "doc_articles"
    id = Column(Integer, primary_key=True)
    titulo = Column(String(180), nullable=False)
    resumen = Column(String(500), nullable=False, default="")
    categoria = Column(String(100), nullable=False, default="General")
    audiencia = Column(String(20), nullable=False, default="general", index=True)
    estado = Column(String(20), nullable=False, default="borrador", index=True)
    contenido = Column(long_text(), nullable=False, default="")
    origen = Column(String(20), nullable=False, default="plataforma")
    ruta_fuente = Column(String(255), nullable=True, unique=True)
    version = Column(Integer, nullable=False, default=1)
    actualizado_en = Column(DateTime, nullable=False, default=utc_now, index=True)
    __mapper_args__ = {"version_id_col": version}


class DocRevision(Base):
    __tablename__ = "doc_revisions"
    __table_args__ = (UniqueConstraint("articulo_id", "version", name="uq_doc_revision_version"),)
    id = Column(Integer, primary_key=True)
    articulo_id = Column(Integer, ForeignKey("doc_articles.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    autor = Column(String(180), nullable=False)
    motivo = Column(String(500), nullable=False)
    snapshot = Column(long_text(), nullable=False)
    creado_en = Column(DateTime, nullable=False, default=utc_now)


class DocComment(Base):
    __tablename__ = "doc_comments"
    id = Column(Integer, primary_key=True)
    articulo_id = Column(Integer, ForeignKey("doc_articles.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    autor = Column(String(180), nullable=False)
    contenido = Column(Text, nullable=False)
    cita = Column(String(2000), nullable=False, default="")
    ancla = Column(JSON, nullable=True)
    version_articulo = Column(Integer, nullable=False)
    estado = Column(String(20), nullable=False, default="abierto")
    creado_en = Column(DateTime, nullable=False, default=utc_now)


class DocAttachment(Base):
    __tablename__ = "doc_attachments"
    id = Column(Integer, primary_key=True)
    articulo_id = Column(Integer, ForeignKey("doc_articles.id"), nullable=False, index=True)
    comentario_id = Column(Integer, ForeignKey("doc_comments.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String(180), nullable=False)
    archivo = Column(String(80), nullable=False, unique=True)
    mime = Column(String(100), nullable=False)
    tamano = Column(Integer, nullable=False)
    uso = Column(String(20), nullable=False)
    creado_en = Column(DateTime, nullable=False, default=utc_now)
