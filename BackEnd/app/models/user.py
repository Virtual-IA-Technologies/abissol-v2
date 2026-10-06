
from sqlalchemy import JSON, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import relationship

from ..utils.time import utc_now

from ..database import Base


class UsuarioRol(Base):
    __tablename__ = "usuario_roles"
    __table_args__ = (
        CheckConstraint(
            "(is_permanent = 1 AND starts_at IS NULL AND ends_at IS NULL) OR "
            "(is_permanent = 0 AND starts_at IS NOT NULL AND ends_at IS NOT NULL AND ends_at > starts_at)",
            name="ck_usuario_roles_vigencia",
        ),
    )
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    rol_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    is_permanent = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    usuario = relationship("Usuario", back_populates="role_assignments", overlaps="roles,usuarios")
    rol = relationship("Rol", back_populates="user_assignments", overlaps="roles,usuarios")


usuario_roles = UsuarioRol.__table__


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("tema IN ('light', 'medium', 'dark', 'virtualia', 'lady')", name="ck_usuarios_tema"),
        CheckConstraint("menu_palette IN ('theme', 'custom')", name="ck_usuarios_menu_palette"),
        CheckConstraint("background_palette IN ('theme', 'custom')", name="ck_usuarios_background_palette"),
        CheckConstraint("navigation_layout IN ('sidebar', 'icons', 'top')", name="ck_usuarios_navigation_layout"),
        CheckConstraint("menu_tone BETWEEN 0 AND 100", name="ck_usuarios_menu_tone"),
        CheckConstraint("background_tone BETWEEN 0 AND 100", name="ck_usuarios_background_tone"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(180), nullable=False)
    legacy_contact_phone = Column(String(100), nullable=True)
    apellido = Column(String(50), nullable=False)
    username = Column(String(40), nullable=False, unique=True, index=True)
    telefono = Column(String(20), nullable=True, unique=True, index=True)
    correo = Column(String(100), nullable=True, unique=True, index=True)
    avatar_file = Column(String(120), nullable=True)
    tema = Column(String(10), nullable=False, default="medium", server_default="medium")
    menu_palette = Column(String(16), nullable=False, default="theme", server_default="theme")
    background_palette = Column(String(16), nullable=False, default="theme", server_default="theme")
    menu_color = Column(String(7), nullable=False, default="#075985", server_default="#075985")
    menu_tone = Column(Integer, nullable=False, default=50, server_default="50")
    background_color = Column(String(7), nullable=False, default="#f3e8ff", server_default="#f3e8ff")
    background_tone = Column(Integer, nullable=False, default=50, server_default="50")
    appearance_overrides = Column(JSON, nullable=False, default=dict, server_default="{}")
    navigation_layout = Column(String(16), nullable=False, default="sidebar", server_default="sidebar")
    escala = Column(Integer, nullable=False, default=100, server_default="100")
    contrasena = Column(String(255), nullable=False)
    fecha_ingreso = Column(Date, nullable=True)
    fecha_registro = Column(TIMESTAMP, nullable=False, default=utc_now)
    fecha_finalizacion = Column(Date, nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    requiere_cambio_clave = Column(Boolean, nullable=False, default=True)
    roles = relationship("Rol", secondary=usuario_roles, back_populates="usuarios", overlaps="role_assignments,usuario,rol,user_assignments")
    role_assignments = relationship(
        "UsuarioRol", back_populates="usuario", cascade="all, delete-orphan",
        overlaps="roles,usuarios",
    )
    accesos = relationship(
        "AccessGrant",
        foreign_keys="AccessGrant.usuario_id",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    @property
    def rol(self):
        return self.roles[0] if self.roles else None

    @property
    def rol_id(self):
        return self.roles[0].id if self.roles else None

    @property
    def rol_ids(self) -> list[int]:
        return [rol.id for rol in self.roles]

    def active_roles(self):
        now = utc_now()
        return [
            assignment.rol
            for assignment in self.role_assignments
            if assignment.is_active
            and assignment.rol.is_active
            and (assignment.is_permanent or (
                assignment.starts_at is not None
                and assignment.ends_at is not None
                and assignment.starts_at <= now < assignment.ends_at
            ))
        ]
