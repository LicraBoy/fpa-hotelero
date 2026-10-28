"""Hoja completa de una sección del Budget (p. ej. *Other Income*): todas sus cuentas por mes y el
bloque inferior de la hoja de Contraloría, replicado tal cual (parte 1b de «Budget por cuenta»).

Bloque inferior, igual que en el Excel (`Other Income`, filas 33 a 41):

- **Mthly**: inflación mensual (fracción, 0.05 = 5 %). Es **informativa**: no cambia el Budget de
  las cuentas (cada una ya trae su propio factor).
- **Cum**: acumulada = suma simple de los meses hasta ése (`Cum = SUM(M33:N33)`, no compuesta).
- **Total con inflación** = total del mes × (1 + Mthly).
- **Est Act** y **Budget** del año previo: referencia (hoy del Excel; ver `HojaSeccionMes.origen`).
- **Variance** = Est Act − Budget previo; **%** = Variance / Budget previo (`None` si éste es 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.ingesta.budget_other_income import OtherIncomeLeido
from fpa.modelos.presupuesto import (
    CicloPresupuesto,
    HojaSeccionMes,
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
)
from fpa.modelos.reporte import LineaReporte
from fpa.modelos.tipos import MICRO
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.presupuesto_distribucion import periodos_de_ano_fiscal

_CERO = Decimal(0)
_PCT = Decimal("0.000001")


class HojaInvalida(Exception):
    """Hoja no válida o fuera de turno. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


@dataclass(frozen=True)
class BloqueInferior:
    total_con_inflacion: list[Decimal]
    acumulada: list[Decimal]
    variacion: list[Decimal | None]
    variacion_pct: list[Decimal | None]


def calcular_bloque(
    totales: Sequence[Decimal],
    inflacion: Sequence[Decimal | None],
    est_act: Sequence[Decimal | None],
    budget_previo: Sequence[Decimal | None],
) -> BloqueInferior:
    """Calcula el bloque inferior mes a mes. Todas las entradas tienen 12 valores."""
    infl = [i or _CERO for i in inflacion]
    acumulada: list[Decimal] = []
    corrido = _CERO
    for i in infl:
        corrido += i
        acumulada.append(corrido)
    con_inflacion = [(t + t * i).quantize(MICRO) for t, i in zip(totales, infl, strict=True)]
    variacion: list[Decimal | None] = []
    pct: list[Decimal | None] = []
    for e, b in zip(est_act, budget_previo, strict=True):
        if e is None or b is None:
            variacion.append(None)
            pct.append(None)
            continue
        v = e - b
        variacion.append(v)
        pct.append((v / b).quantize(_PCT) if b != 0 else None)
    return BloqueInferior(con_inflacion, acumulada, variacion, pct)


@dataclass(frozen=True)
class CuentaHoja:
    linea_id: int
    descripcion: str
    codigo: str | None
    estado: str
    meses: list[Decimal | None]


@dataclass(frozen=True)
class HojaSalida:
    seccion_id: int
    seccion: str
    periodos: list[str]
    cuentas: list[CuentaHoja]
    totales: list[Decimal]
    inflacion: list[Decimal | None]
    est_act: list[Decimal | None]
    budget_previo: list[Decimal | None]
    origen: str | None
    bloque: BloqueInferior


def _seccion_y_lineas(
    db: Session, ciclo: CicloPresupuesto, seccion_id: int
) -> tuple[LineaReporte, list[LineaReporte]]:
    if ciclo.version_estructura_id is None:
        raise HojaInvalida(409, "El ciclo no tiene una estructura de reporte asociada")
    lineas = RepositorioReporte(db, ciclo.hotel_id).lineas(ciclo.version_estructura_id)
    seccion = next((x for x in lineas if x.id == seccion_id and x.tipo == "seccion"), None)
    if seccion is None:
        raise LookupError("Sección no encontrada")
    detalle = [x for x in lineas if x.tipo == "detalle" and x.seccion_id == seccion_id]
    return seccion, detalle


def _filas_hoja(db: Session, ciclo_id: int, seccion_id: int) -> dict[str, HojaSeccionMes]:
    return {
        f.periodo: f
        for f in db.scalars(
            select(HojaSeccionMes).where(
                HojaSeccionMes.ciclo_id == ciclo_id, HojaSeccionMes.seccion_linea_id == seccion_id
            )
        )
    }


def leer_hoja(
    db: Session, *, hotel_id: int, ciclo_id: int, seccion_id: int, visibles: set[int] | None
) -> HojaSalida:
    ciclo = db.get(CicloPresupuesto, ciclo_id)
    if ciclo is None or ciclo.hotel_id != hotel_id:
        raise LookupError("Ciclo de presupuesto no encontrado")
    seccion, detalle = _seccion_y_lineas(db, ciclo, seccion_id)
    if visibles is not None:
        detalle = [x for x in detalle if x.id in visibles]
        if not detalle:
            raise LookupError("Sección no encontrada")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    capturas = {
        c.linea_id: c
        for c in db.scalars(
            select(LineaPresupuestoCaptura).where(LineaPresupuestoCaptura.ciclo_id == ciclo_id)
        )
    }
    cuentas: list[CuentaHoja] = []
    totales = [_CERO] * 12
    for linea in detalle:
        captura = capturas.get(linea.id)
        por_periodo: dict[str, Decimal] = {}
        if captura is not None:
            por_periodo = {
                m.periodo: m.importe
                for m in db.scalars(
                    select(LineaPresupuestoMensual).where(
                        LineaPresupuestoMensual.linea_captura_id == captura.id
                    )
                )
            }
        meses = [por_periodo.get(p) for p in periodos]
        for i, m in enumerate(meses):
            if m is not None:
                totales[i] += m
        cuentas.append(
            CuentaHoja(
                linea_id=linea.id,
                descripcion=linea.descripcion,
                codigo=linea.codigo_corporativo,
                estado=captura.estado if captura else "pendiente",
                meses=meses,
            )
        )
    filas = _filas_hoja(db, ciclo_id, seccion_id)
    inflacion = [filas[p].inflacion if p in filas else None for p in periodos]
    est_act = [filas[p].est_act_total if p in filas else None for p in periodos]
    previo = [filas[p].budget_previo_total if p in filas else None for p in periodos]
    return HojaSalida(
        seccion_id=seccion_id,
        seccion=seccion.descripcion,
        periodos=periodos,
        cuentas=cuentas,
        totales=totales,
        inflacion=inflacion,
        est_act=est_act,
        budget_previo=previo,
        origen=next((f.origen for f in filas.values()), None),
        bloque=calcular_bloque(totales, inflacion, est_act, previo),
    )


def _fila(db: Session, ciclo_id: int, seccion_id: int, periodo: str) -> HojaSeccionMes:
    fila = db.scalar(
        select(HojaSeccionMes).where(
            HojaSeccionMes.ciclo_id == ciclo_id,
            HojaSeccionMes.seccion_linea_id == seccion_id,
            HojaSeccionMes.periodo == periodo,
        )
    )
    if fila is None:
        fila = HojaSeccionMes(ciclo_id=ciclo_id, seccion_linea_id=seccion_id, periodo=periodo)
        db.add(fila)
    return fila


def guardar_inflacion(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    seccion_id: int,
    inflacion: dict[str, Decimal],
    visibles: set[int] | None,
) -> None:
    """Reemplaza **completa** la inflación mensual de la hoja (12 meses; no es parcial)."""
    ciclo = db.get(CicloPresupuesto, ciclo_id)
    if ciclo is None or ciclo.hotel_id != hotel_id:
        raise LookupError("Ciclo de presupuesto no encontrado")
    _, detalle = _seccion_y_lineas(db, ciclo, seccion_id)
    if visibles is not None and not any(x.id in visibles for x in detalle):
        raise LookupError("Sección no encontrada")
    if ciclo.estado != "borrador":
        raise HojaInvalida(409, "El ciclo no está en captura")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    if set(inflacion) != set(periodos):
        raise HojaInvalida(422, "Hay que dar la inflación de cada uno de los 12 periodos")
    if any(v < -1 or v > 1 for v in inflacion.values()):
        raise HojaInvalida(422, "La inflación mensual debe estar entre -100 % y 100 %")
    for p in periodos:
        _fila(db, ciclo_id, seccion_id, p).inflacion = inflacion[p].quantize(MICRO)
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.hoja_inflacion",
        entidad="hoja_seccion_mes",
        entidad_id=ciclo_id,
        detalle={"seccion_id": seccion_id},
    )


def guardar_referencias_excel(
    db: Session, *, ciclo: CicloPresupuesto, seccion_id: int, leido: OtherIncomeLeido
) -> int:
    """Guarda lo que trae el bloque inferior del Excel (inflación, Est Act y Budget previo)."""
    if leido.inflacion is None and leido.est_act is None and leido.budget_previo is None:
        return 0
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    for i, p in enumerate(periodos):
        fila = _fila(db, ciclo.id, seccion_id, p)
        if leido.inflacion is not None:
            fila.inflacion = leido.inflacion[i]
        if leido.est_act is not None:
            fila.est_act_total = leido.est_act[i]
        if leido.budget_previo is not None:
            fila.budget_previo_total = leido.budget_previo[i]
        fila.origen = "excel"
    db.flush()
    return len(periodos)
