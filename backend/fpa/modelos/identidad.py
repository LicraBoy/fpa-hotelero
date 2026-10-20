from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
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
    # Credenciales locales (ADR 0005). Nunca se devuelven por la API.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_cambiada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secreto: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_activo: Mapped[bool] = mapped_column(Boolean, default=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Asignacion(Base):
    """Qué rol tiene un usuario en un hotel. Sin asignación no hay acceso (deny by default)."""

    __tablename__ = "asignacion"
    __table_args__ = (UniqueConstraint("usuario_id", "hotel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id"))


class Sesion(Base):
    """Sesión abierta de un usuario. Solo se guarda el SHA-256 del token que tiene el navegador."""

    __tablename__ = "sesion"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agente: Mapped[str | None] = mapped_column(String(200), nullable=True)
