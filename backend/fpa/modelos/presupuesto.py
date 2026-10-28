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
    false,
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
    # La cuenta se captura por PARTIDAS (Cant. × Costo + reparto mensual + inflación): su Budget sale
    # de `PartidaLinea` (`fpa.servicios.presupuesto_partidas`) y no se edita mes a mes.
    usa_partidas: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


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


METODOS_DETALLE = ("factor", "fijo")


class DetalleLineaPresupuesto(Base):
    """La tabla interna de una línea en captura (p. ej. *Other Income*): cómo se obtuvo el importe
    de cada mes. `factor`: `importe = base × factor` (la base es el Est-Act del año previo);
    `fijo`: `importe = monto_fijo`. Guardarlo fija también `propuesta_anual` y los
    `LineaPresupuestoMensual` de la línea (`fpa.servicios.presupuesto_detalle`), así que aprobar el
    ciclo no cambia. Cualquier otra forma de mensualizar la línea borra este detalle."""

    __tablename__ = "linea_presupuesto_detalle"
    __table_args__ = (UniqueConstraint("linea_captura_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_captura_id: Mapped[int] = mapped_column(
        ForeignKey("linea_presupuesto_captura.id"), index=True
    )
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    metodo: Mapped[str] = mapped_column(String(6))
    base: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    factor: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    monto_fijo: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    importe: Mapped[Decimal] = mapped_column(Medida)


class LineaPlanDetalle(Base):
    """Copia **inmutable** del detalle de una línea al aprobar el ciclo (ADR 0003): ligada a la
    `VersionPlan` que produjo el ciclo, así reabrir y volver a editar el ciclo no altera lo que
    sustentó una versión ya emitida."""

    __tablename__ = "linea_plan_detalle"
    __table_args__ = (UniqueConstraint("version_plan_id", "linea_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_plan_id: Mapped[int] = mapped_column(ForeignKey("version_plan.id"), index=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("linea_reporte.id"))
    periodo: Mapped[str] = mapped_column(String(7))
    metodo: Mapped[str] = mapped_column(String(6))
    base: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    factor: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    monto_fijo: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    importe: Mapped[Decimal] = mapped_column(Medida)


class HojaSeccionMes(Base):
    """Bloque inferior de la hoja de una sección (*Other Income*), por mes: la inflación mensual
    (informativa: no cambia el Budget, igual que en el Excel de Contraloría) y los comparativos del
    año previo — el Est-Act y el Budget previo. `origen`: `excel` hoy; luego el Budget previo saldrá
    de la `VersionPlan` del año anterior y el Est-Act de su propia carga."""

    __tablename__ = "hoja_seccion_mes"
    __table_args__ = (UniqueConstraint("ciclo_id", "seccion_linea_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo_presupuesto.id"), index=True)
    seccion_linea_id: Mapped[int] = mapped_column(ForeignKey("linea_reporte.id"))
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    inflacion: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)  # 0.05 = 5 %
    est_act_total: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    budget_previo_total: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    origen: Mapped[str] = mapped_column(String(10), default="excel")


METODOS_PARTIDA = ("mensual", "estacional", "importada")


class PartidaLinea(Base):
    """Una partida de la tabla de una cuenta (p. ej. *Other Fringe*: «PARTY ROOM», qty 1, costo 162,750).

    **Costo extendido = cantidad × costo** (derivado, nunca se guarda). `metodo`: `mensual` (el
    extendido entre 12), `estacional` (los meses que se capturan en `PartidaMes`) o `importada`
    (meses del Excel de solo lectura, p. ej. los que reparte «Md Pts»).
    """

    __tablename__ = "linea_presupuesto_partida"

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_captura_id: Mapped[int] = mapped_column(
        ForeignKey("linea_presupuesto_captura.id"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer)
    concepto: Mapped[str] = mapped_column(String(120))
    cantidad: Mapped[Decimal] = mapped_column(Medida)
    unidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    costo: Mapped[Decimal] = mapped_column(Medida)
    metodo: Mapped[str] = mapped_column(String(10))


class PartidaMes(Base):
    """Importe de una partida `estacional` o `importada` en un mes."""

    __tablename__ = "linea_presupuesto_partida_mes"
    __table_args__ = (UniqueConstraint("partida_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    partida_id: Mapped[int] = mapped_column(ForeignKey("linea_presupuesto_partida.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    importe: Mapped[Decimal] = mapped_column(Medida)


class InflacionLineaMes(Base):
    """Inflación mensual de una cuenta con partidas (0.05 = 5 %). **Sí entra al Budget**: Budget del
    mes = distribución × (1 + tasa), igual que en las hojas de detalle del Excel."""

    __tablename__ = "linea_presupuesto_inflacion_mes"
    __table_args__ = (UniqueConstraint("linea_captura_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_captura_id: Mapped[int] = mapped_column(
        ForeignKey("linea_presupuesto_captura.id"), index=True
    )
    periodo: Mapped[str] = mapped_column(String(7))
    tasa: Mapped[Decimal] = mapped_column(Medida)


class ReferenciaLineaMes(Base):
    """Comparativos del año previo de una cuenta, por mes: Est-Act y Budget previo (del Excel)."""

    __tablename__ = "linea_presupuesto_referencia_mes"
    __table_args__ = (UniqueConstraint("linea_captura_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_captura_id: Mapped[int] = mapped_column(
        ForeignKey("linea_presupuesto_captura.id"), index=True
    )
    periodo: Mapped[str] = mapped_column(String(7))
    est_act: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    budget_previo: Mapped[Decimal | None] = mapped_column(Medida, nullable=True)
    origen: Mapped[str] = mapped_column(String(10), default="excel")
