from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc


class Organizacion(Base):
    """Cliente de la plataforma (hoy: Torres Mazatlan S.A. de C.V.). Sus datos están aislados."""

    __tablename__ = "organizacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), unique=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class Hotel(Base):
    __tablename__ = "hotel"
    __table_args__ = (UniqueConstraint("organizacion_id", "codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizacion.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(200))
    # [POR VALIDAR con Contraloría] el año fiscal del Variance parece julio–junio.
    mes_inicio_anio_fiscal: Mapped[int] = mapped_column(Integer, default=7)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
