from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class Rol(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    prioridad = Column(Integer, nullable=False, default=100)
    es_superusuario = Column(Boolean, nullable=False, default=False)
    usuarios = relationship("Usuario", secondary="usuario_roles", back_populates="roles", overlaps="role_assignments,usuario,rol,user_assignments")
    user_assignments = relationship("UsuarioRol", back_populates="rol", overlaps="roles,usuarios")
    accesos = relationship("AccessGrant", back_populates="rol", cascade="all, delete-orphan")

    @property
    def user_ids(self) -> list[int]:
        return [usuario.id for usuario in self.usuarios]
