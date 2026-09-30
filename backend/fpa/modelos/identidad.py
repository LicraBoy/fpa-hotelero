from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc


class Rol(Base):
    """Rol funcional. Los permisos de cada rol viven en `fpa.identidad.permisos`."""

    __tablename__ = "rol"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizacion.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class Asignacion(Base):
    """Qué rol tiene un usuario en un hotel. Sin asignación no hay acceso (deny by default)."""

    __tablename__ = "asignacion"
    __table_args__ = (UniqueConstraint("usuario_id", "hotel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id"))
