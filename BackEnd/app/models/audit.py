
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from ..utils.time import utc_now

from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    actor_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    impersonacion_id = Column(Integer, ForeignKey("impersonation_sessions.id"), nullable=True, index=True)
    accion = Column(String(80), nullable=False, index=True)
    modulo = Column(String(80), nullable=False, default="core", index=True)
    entidad = Column(String(80), nullable=False, index=True)
    entidad_id = Column(String(80), nullable=True, index=True)
    detalle = Column(Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(80), nullable=True, index=True)
    metodo = Column(String(10), nullable=True)
    ruta = Column(String(255), nullable=True)
    estado_http = Column(Integer, nullable=True)
    datos_antes = Column(Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=True)
    datos_despues = Column(Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=True)
    creado_en = Column(DateTime, nullable=False, default=utc_now, index=True)
