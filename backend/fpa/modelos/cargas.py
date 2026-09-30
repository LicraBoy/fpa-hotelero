"""Cargas de archivos y sus movimientos contables (Actuals).

Regla (ADR 0003): una `CargaArchivo` por (archivo, periodo) y **una sola vigente por
(hotel, periodo)**. Recargar un periodo deja la anterior como `reemplazada` (historial).
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc
from fpa.modelos.tipos import Dinero, Medida


class EstadoCarga(StrEnum):
    VIGENTE = "vigente"
    REEMPLAZADA = "reemplazada"


class CargaArchivo(Base):
    __tablename__ = "carga_archivo"
    __table_args__ = (
        # Solo una carga vigente por hotel y periodo (defensa a nivel de base de datos).
        Index(
            "uq_carga_vigente_hotel_periodo",
            "hotel_id",
            "periodo",
            unique=True,
            sqlite_where=text("estado = 'vigente'"),
            postgresql_where=text("estado = 'vigente'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    fuente: Mapped[str] = mapped_column(String(40))
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    tamano_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    fecha_min: Mapped[date] = mapped_column(Date)
    fecha_max: Mapped[date] = mapped_column(Date)
    n_movimientos: Mapped[int] = mapped_column(Integer)
    total_debito: Mapped[Decimal] = mapped_column(Dinero)
    total_credito: Mapped[Decimal] = mapped_column(Dinero)
    estado: Mapped[str] = mapped_column(String(20), default=EstadoCarga.VIGENTE.value)
    controles: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    reemplazada_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("carga_archivo.id"), nullable=True
    )
    reemplazada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Movimiento(Base):
    __tablename__ = "movimiento"
    __table_args__ = (
        Index("ix_movimiento_hotel_periodo_cuenta", "hotel_id", "periodo", "cuenta_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    carga_id: Mapped[int] = mapped_column(ForeignKey("carga_archivo.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"))
    periodo: Mapped[str] = mapped_column(String(7))
    cuenta_codigo: Mapped[str] = mapped_column(String(40))
    cuenta_descripcion: Mapped[str] = mapped_column(String(300))
    fecha: Mapped[date] = mapped_column(Date)
    asiento: Mapped[str] = mapped_column(String(40))
    tp_asiento: Mapped[str | None] = mapped_column(String(40), nullable=True)
    operacion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tp_doc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(60), nullable=True)
    concepto: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debito: Mapped[Decimal] = mapped_column(Dinero)
    credito: Mapped[Decimal] = mapped_column(Dinero)
    saldo: Mapped[Decimal | None] = mapped_column(Dinero, nullable=True)
    cantidad: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    costo: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    fila_origen: Mapped[int] = mapped_column(Integer)
