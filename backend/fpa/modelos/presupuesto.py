"""Calendario fiscal y ciclo de captura del Budget (Fase 7.1, Blueprint §7 Budget en la plataforma).

Principio del diseño (`docs/DISENO_FASE7_BUDGET.md` §1): esta capa solo cambia **cómo se produce**
el Budget, no cómo se consume. Al aprobar un `CicloPresupuesto` se genera una `VersionPlan` normal
(`fpa.modelos.plan`) — Variance sigue leyendo esa tabla sin importarle el origen. Esa generación es
de la Fase 7.4; aquí solo viven los modelos, sin ese paso todavía.

Ciclo: `borrador` (captura) -> `enviado` -> `revision` -> `aprobado` -> `bloqueado`, con «devolver»
(Enviado/Revisión -> Borrador) y «reabrir» (Aprobado -> Borrador), ambas con nota obligatoria — el
mismo patrón que `fpa.modelos.cierre.CierrePeriodo`. `CicloTransicion` solo se inserta.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from fpa.modelos.base import Base, ahora_utc
from fpa.modelos.cierre import TransicionInmutable
from fpa.modelos.tipos import Medida

ESTADOS_CICLO = ("borrador", "enviado", "revision", "aprobado", "bloqueado")


class AnoFiscal(Base):
    """Año fiscal de un hotel (p. ej. julio a junio). `[POR VALIDAR con Contraloría]`."""

    __tablename__ = "ano_fiscal"
    __table_args__ = (UniqueConstraint("hotel_id", "etiqueta"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    etiqueta: Mapped[str] = mapped_column(String(9))  # p. ej. "2026/27"
    mes_inicio: Mapped[int] = mapped_column(Integer)
    mes_fin: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(10), default="abierto")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class PeriodoFiscal(Base):
    """Un mes dentro de un `AnoFiscal`.

    `estado` pasa a `cerrado` cuando el `CierrePeriodo` del Variance de ese mes llega a
    aprobado/bloqueado — enlace lógico entre módulos, sin FK dura (los ids de línea y de cierre
    cambian de dominio). Esa sincronización automática no se implementa en 7.1: el campo se deja
    manipulable directamente hasta que una fase posterior la añada.
    """

    __tablename__ = "periodo_fiscal"
    __table_args__ = (UniqueConstraint("ano_fiscal_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ano_fiscal_id: Mapped[int] = mapped_column(ForeignKey("ano_fiscal.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    estado: Mapped[str] = mapped_column(String(10), default="abierto")
    fecha_limite: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cerrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)


class CicloPresupuesto(Base):
    __tablename__ = "ciclo_presupuesto"
    __table_args__ = (UniqueConstraint("hotel_id", "ano_fiscal_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    ano_fiscal_id: Mapped[int] = mapped_column(ForeignKey("ano_fiscal.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)  # consecutivo por hotel y año fiscal
    estado: Mapped[str] = mapped_column(String(12), default="borrador")
    version_estructura_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_estructura_reporte.id"), nullable=True
    )
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    aprobado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Se llena al aprobar (Fase 7.4): la VersionPlan que este ciclo produjo.
    version_plan_resultante_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_plan.id"), nullable=True
    )


class CicloTransicion(Base):
    """Cada cambio de estado del ciclo, con quién lo hizo y su nota. Solo se inserta."""

    __tablename__ = "ciclo_transicion"

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo_presupuesto.id"), index=True)
    desde: Mapped[str] = mapped_column(String(12))
    hacia: Mapped[str] = mapped_column(String(12))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


@event.listens_for(CicloTransicion, "before_update")
def _prohibir_update(mapper: Mapper[Any], connection: Connection, target: CicloTransicion) -> None:
    raise TransicionInmutable("Las transiciones de ciclo de presupuesto no se pueden modificar")


@event.listens_for(CicloTransicion, "before_delete")
def _prohibir_delete(mapper: Mapper[Any], connection: Connection, target: CicloTransicion) -> None:
    raise TransicionInmutable("Las transiciones de ciclo de presupuesto no se pueden borrar")


class PerfilDistribucion(Base):
    """Perfil de prorrateo mensual reutilizable (p. ej. mantenimiento: 5/5/8/82 % por estación).

    `pesos` son 12 decimales que deben sumar 1.000000 — la validación vive en el servicio de la
    Fase 7.3, no aquí. `hotel_id` nulo = disponible para todos los hoteles.
    """

    __tablename__ = "perfil_distribucion"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int | None] = mapped_column(ForeignKey("hotel.id"), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    pesos: Mapped[list[str]] = mapped_column(JSON)
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False)


class LineaPresupuestoCaptura(Base):
    """Una línea de detalle del reporte dentro de un ciclo: objetivo de Dirección y propuesta
    del responsable de departamento. La resolución de `responsable_id` a partir de la sección de
    la línea (vía `AsignacionDepartamento`) es de la Fase 7.2."""

    __tablename__ = "linea_presupuesto_captura"
    __table_args__ = (UniqueConstraint("ciclo_id", "linea_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo_presupuesto.id"), index=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("linea_reporte.id"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    objetivo: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    propuesta_anual: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    perfil_distribucion_id: Mapped[int | None] = mapped_column(
        ForeignKey("perfil_distribucion.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)


class LineaPresupuestoMensual(Base):
    """El prorrateo mensual de una `LineaPresupuestoCaptura` (Fase 7.3): la suma de los 12 meses
    debe ser exactamente igual a `propuesta_anual` (criterio de aceptación 1 de la Fase 7)."""

    __tablename__ = "linea_presupuesto_mensual"
    __table_args__ = (UniqueConstraint("linea_captura_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_captura_id: Mapped[int] = mapped_column(
        ForeignKey("linea_presupuesto_captura.id"), index=True
    )
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    importe: Mapped[Decimal] = mapped_column(Medida)
