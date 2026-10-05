from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.time import utc_now


calendar_event_assignees = Table(
    "calendar_event_assignees",
    Base.metadata,
    Column("event_id", ForeignKey("calendar_events.id", ondelete="CASCADE"), primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
)

calendar_event_labels = Table(
    "calendar_event_labels",
    Base.metadata,
    Column("event_id", ForeignKey("calendar_events.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", ForeignKey("calendar_labels.id", ondelete="CASCADE"), primary_key=True),
)


class CalendarLabel(Base):
    __tablename__ = "calendar_labels"
    __table_args__ = (UniqueConstraint("nombre", name="uq_calendar_labels_nombre"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(60), nullable=False)
    color = Column(String(7), nullable=False, default="#2563eb")
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'confirmado', 'en_progreso', 'completado', 'cancelado')",
            name="ck_calendar_events_estado",
        ),
        CheckConstraint(
            "prioridad IN ('baja', 'media', 'alta', 'urgente')",
            name="ck_calendar_events_prioridad",
        ),
        CheckConstraint(
            "visibilidad IN ('personal', 'equipo')",
            name="ck_calendar_events_visibilidad",
        ),
        CheckConstraint("fin > inicio", name="ck_calendar_events_periodo"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    titulo = Column(String(160), nullable=False)
    descripcion = Column(Text, nullable=True)
    inicio = Column(DateTime, nullable=False, index=True)
    fin = Column(DateTime, nullable=False, index=True)
    todo_el_dia = Column(Boolean, nullable=False, default=False)
    estado = Column(String(20), nullable=False, default="pendiente", index=True)
    prioridad = Column(String(10), nullable=False, default="media", index=True)
    visibilidad = Column(String(10), nullable=False, default="equipo", index=True)
    ubicacion = Column(String(200), nullable=True)
    propietario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    origen_modulo = Column(String(80), nullable=True, index=True)
    origen_tipo = Column(String(80), nullable=True)
    origen_id = Column(String(80), nullable=True)
    origen_url = Column(String(255), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    propietario = relationship("Usuario", foreign_keys=[propietario_id])
    asignados = relationship("Usuario", secondary=calendar_event_assignees)
    etiquetas = relationship("CalendarLabel", secondary=calendar_event_labels)
    recordatorios = relationship("CalendarReminder", back_populates="evento", cascade="all, delete-orphan")


class CalendarReminder(Base):
    __tablename__ = "calendar_reminders"
    __table_args__ = (
        CheckConstraint("minutos_antes >= 0", name="ck_calendar_reminders_minutos"),
        CheckConstraint("canal IN ('interno', 'correo')", name="ck_calendar_reminders_canal"),
        UniqueConstraint("event_id", "minutos_antes", "canal", name="uq_calendar_reminder"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False, index=True)
    minutos_antes = Column(Integer, nullable=False)
    canal = Column(String(10), nullable=False, default="interno")
    enviado_at = Column(DateTime, nullable=True)

    evento = relationship("CalendarEvent", back_populates="recordatorios")
