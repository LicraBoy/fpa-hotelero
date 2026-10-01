"""Versiones del plan (Budget) por hotel. **Una versión nunca se edita.**

Cada importación crea una `VersionPlan` nueva; si ya había una vigente para el mismo año fiscal,
queda como `reemplazada` (historial). Las cifras (`LineaPlan`) se guardan **tal como vienen del
Excel**, con hasta 6 decimales (`Medida`): el Budget del Excel trae decimales de más y recortarlo a
centavos cambiaría los totales. Los reportes redondean al mostrar.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc
from fpa.modelos.tipos import Medida

TIPO_BUDGET = "budget"
VIGENTE = "vigente"
REEMPLAZADA = "reemplazada"


class VersionPlan(Base):
    __tablename__ = "version_plan"
    __table_args__ = (
        # Una sola versión vigente por hotel, tipo y año fiscal (defensa en la base de datos)
        Index(
            "uq_plan_vigente_hotel_tipo_anio",
            "hotel_id",
            "tipo",
            "ano_fiscal",
            unique=True,
            sqlite_where=text("estado = 'vigente'"),
            postgresql_where=text("estado = 'vigente'"),
        ),
        UniqueConstraint("hotel_id", "tipo", "numero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default=TIPO_BUDGET)
    numero: Mapped[int] = mapped_column(Integer)  # consecutivo por hotel y tipo
    ano_fiscal: Mapped[str] = mapped_column(String(9))  # 2026/27
    periodo_corte: Mapped[str] = mapped_column(String(7))  # AAAA-MM del archivo
    version_estructura_id: Mapped[int] = mapped_column(ForeignKey("version_estructura_reporte.id"))
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    estado: Mapped[str] = mapped_column(String(20), default=VIGENTE)
    n_lineas: Mapped[int] = mapped_column(Integer)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    reemplazada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LineaPlan(Base):
    """Budget de una línea del reporte: mes del corte, acumulado del año fiscal y anual."""

    __tablename__ = "linea_plan"
    __table_args__ = (UniqueConstraint("version_plan_id", "linea_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_plan_id: Mapped[int] = mapped_column(ForeignKey("version_plan.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("linea_reporte.id"))
    mes: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    ytd: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    anual: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
