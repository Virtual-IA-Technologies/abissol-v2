
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from ..utils.time import utc_now

from ..database import Base


class DevopsActionLog(Base):
    __tablename__ = "devops_action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    accion = Column(String(30), nullable=False, index=True)
    estado = Column(String(20), nullable=False, index=True)
    mensaje = Column(String(500), nullable=False)
    commit_hash = Column(String(40), nullable=True)
    salida = Column(Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=True)
    creado_en = Column(DateTime, nullable=False, default=utc_now, index=True)
