"""Cierre de un periodo del Variance (Blueprint §29, Fase 5.4).

Un periodo pasa por Borrador → Comentado → Revisado → Aprobado → Bloqueado. Al **aprobar** se
congelan las versiones que produjeron las cifras (mapeo, Budget, estructura y las cargas vigentes
de cada mes del acumulado, con su hash) y una huella de las cifras mismas. Mientras esté aprobado
o bloqueado, el Variance del periodo se calcula con esas versiones y no se aceptan recargas.
Cada paso queda en `CierreTransicion`, que solo se inserta.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from fpa.modelos.base import Base, ahora_utc

ESTADOS_CIERRE = ("borrador", "comentado", "revisado", "aprobado", "bloqueado")
ESTADOS_CERRADOS = ("aprobado", "bloqueado")


class CierrePeriodo(Base):
    __tablename__ = "cierre_periodo"
    __table_args__ = (UniqueConstraint("hotel_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    estado: Mapped[str] = mapped_column(String(12), default="borrador")
    # Se llenan al aprobar y se conservan aunque luego se reabra (son el rastro de la aprobación)
    version_mapeo_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_mapeo.id"), nullable=True
    )
    version_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_plan.id"), nullable=True
    )
    version_estructura_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_estructura_reporte.id"), nullable=True
    )
    congelado: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    huella_cifras: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class CierreTransicion(Base):
    """Cada cambio de estado, con quién lo hizo y su nota. Solo se inserta."""

    __tablename__ = "cierre_transicion"

    id: Mapped[int] = mapped_column(primary_key=True)
    cierre_id: Mapped[int] = mapped_column(ForeignKey("cierre_periodo.id"), index=True)
    desde: Mapped[str] = mapped_column(String(12))
    hacia: Mapped[str] = mapped_column(String(12))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class TransicionInmutable(RuntimeError):
    """Se intentó modificar o borrar una transición de cierre."""


@event.listens_for(CierreTransicion, "before_update")
def _prohibir_update(mapper: Mapper[Any], connection: Connection, target: CierreTransicion) -> None:
    raise TransicionInmutable("Las transiciones de cierre no se pueden modificar")


@event.listens_for(CierreTransicion, "before_delete")
def _prohibir_delete(mapper: Mapper[Any], connection: Connection, target: CierreTransicion) -> None:
    raise TransicionInmutable("Las transiciones de cierre no se pueden borrar")
