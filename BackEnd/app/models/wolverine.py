
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..utils.time import utc_now

from ..database import Base


class Menu(Base):
    """Opción navegable y unidad estable de autorización de Wolverine."""

    __tablename__ = "menus"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('seccion', 'modulo', 'menu', 'submenu', 'pestana')",
            name="ck_menus_tipo",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=True, index=True)
    nombre = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    ruta = Column(String(180), nullable=True, unique=True)
    icono = Column(String(60), nullable=True)
    tipo = Column(String(12), nullable=False, default="menu")
    orden = Column(Integer, nullable=False, default=0)
    is_visible = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)

    parent = relationship("Menu", remote_side=[id], back_populates="children")
    children = relationship("Menu", back_populates="parent", passive_deletes=True)
    accesos = relationship("AccessGrant", back_populates="menu", cascade="all, delete-orphan")


class AccessGrant(Base):
    """Acceso temporal o permanente asignado a un rol o a un usuario."""

    __tablename__ = "access_grants"
    __table_args__ = (
        CheckConstraint(
            "(role_id IS NOT NULL AND usuario_id IS NULL) OR "
            "(role_id IS NULL AND usuario_id IS NOT NULL)",
            name="ck_access_grants_single_subject",
        ),
        CheckConstraint(
            "access_level IN ('none', 'lector', 'editor', 'gestor')",
            name="ck_access_grants_level",
        ),
        UniqueConstraint("role_id", "menu_id", name="uq_access_grants_role_menu"),
        UniqueConstraint("usuario_id", "menu_id", name="uq_access_grants_user_menu"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False, index=True)
    access_level = Column(String(10), nullable=False, default="none")
    starts_at = Column(DateTime, nullable=True, index=True)
    ends_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    rol = relationship("Rol", back_populates="accesos")
    usuario = relationship("Usuario", foreign_keys=[usuario_id], back_populates="accesos")
    menu = relationship("Menu", back_populates="accesos")


class ImpersonationSession(Base):
    """Registra quién asumió otra identidad, durante cuánto tiempo y desde qué sesión."""

    __tablename__ = "impersonation_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    impersonator_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    impersonated_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    device_session_id = Column(Integer, ForeignKey("device_sessions.id"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=utc_now)
    ended_at = Column(DateTime, nullable=True, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)


class LoginAttempt(Base):
    """Contador compacto para frenar intentos de acceso automatizados."""

    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier_hash = Column(String(64), nullable=False, unique=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    lock_until = Column(DateTime, nullable=True, index=True)
    last_attempt_at = Column(DateTime, nullable=False, default=utc_now)
    ip_address = Column(String(64), nullable=True)
