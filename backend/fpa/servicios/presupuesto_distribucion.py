"""Perfiles de distribución y prorrateo mensual del Budget (Fase 7.3).

Reparte el `propuesta_anual` de una `LineaPresupuestoCaptura` en los 12
`LineaPresupuestoMensual` de su año fiscal, por un `PerfilDistribucion` (estacional) o con importes
dados a mano. En ambos casos la suma debe cuadrar **exactamente** con `propuesta_anual` (criterio
de aceptación 1 de la Fase 7): el residuo de redondeo de un reparto por perfil se ajusta en el
último mes con peso distinto de cero; un reparto a mano que no cuadra es error del usuario.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fpa.modelos.presupuesto import (
    CicloPresupuesto,
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
    PerfilDistribucion,
    PeriodoFiscal,
)
from fpa.modelos.tipos import MICRO
from fpa.servicios.auditoria import auditar

NOMBRE_UNIFORME = "Uniforme"
_PESOS_UNIFORME: tuple[Decimal, ...] = (Decimal("0.083333"),) * 11 + (Decimal("0.083337"),)


class DistribucionInvalida(Exception):
    """Reparto no válido. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


def validar_pesos(pesos: Sequence[Decimal]) -> None:
    if len(pesos) != 12:
        raise DistribucionInvalida(422, "El perfil debe tener exactamente 12 pesos, uno por mes")
    if any(p < 0 or p > 1 for p in pesos):
        raise DistribucionInvalida(422, "Cada peso debe estar entre 0 y 1")
    total = sum(pesos, Decimal(0)).quantize(MICRO)
    if total != Decimal("1.000000"):
        raise DistribucionInvalida(422, f"Los pesos deben sumar 1.000000 (suman {total})")


def crear_perfil(
    db: Session,
    *,
    hotel_id: int | None,
    nombre: str,
    pesos: Sequence[Decimal],
    es_sistema: bool = False,
) -> PerfilDistribucion:
    validar_pesos(pesos)
    perfil = PerfilDistribucion(
        hotel_id=hotel_id,
        nombre=nombre,
        pesos=[format(p, "f") for p in pesos],
        es_sistema=es_sistema,
    )
    db.add(perfil)
    db.flush()
    return perfil


def sembrar_perfiles_sistema(db: Session) -> dict[str, PerfilDistribucion]:
    """Siembra los perfiles de sistema (idempotente, igual que `fpa.semilla.sembrar_roles`)."""
    existentes = {
        p.nombre: p
        for p in db.scalars(
            select(PerfilDistribucion).where(PerfilDistribucion.es_sistema.is_(True))
        )
    }
    if NOMBRE_UNIFORME not in existentes:
        existentes[NOMBRE_UNIFORME] = crear_perfil(
            db, hotel_id=None, nombre=NOMBRE_UNIFORME, pesos=_PESOS_UNIFORME, es_sistema=True
        )
    return existentes


def periodos_de_ano_fiscal(db: Session, ano_fiscal_id: int) -> list[str]:
    periodos = list(
        db.scalars(
            select(PeriodoFiscal.periodo)
            .where(PeriodoFiscal.ano_fiscal_id == ano_fiscal_id)
            .order_by(PeriodoFiscal.periodo)
        )
    )
    if len(periodos) != 12:
        raise DistribucionInvalida(
            409, f"El año fiscal necesita sus 12 periodos capturados (tiene {len(periodos)})"
        )
    return periodos


def repartir(anual: Decimal, pesos: Sequence[Decimal]) -> list[Decimal]:
    """Reparte `anual` según `pesos` (12 valores que suman 1): la suma del resultado es exacta.

    El redondeo a 6 decimales de cada mes puede dejar un residuo frente a `anual`; ese residuo se
    suma al último mes con peso distinto de cero (regla simple y documentada, nunca se deja como una
    diferencia silenciosa).
    """
    if len(pesos) != 12:
        raise DistribucionInvalida(422, "El perfil debe tener exactamente 12 pesos, uno por mes")
    importes = [(anual * peso).quantize(MICRO) for peso in pesos]
    diferencia = anual - sum(importes, Decimal(0))
    if diferencia != 0:
        indices_con_peso = [i for i, peso in enumerate(pesos) if peso != 0]
        indice = indices_con_peso[-1] if indices_con_peso else 11
        importes[indice] += diferencia
    return importes


def _captura_y_ciclo(
    db: Session, hotel_id: int, linea_captura_id: int
) -> tuple[LineaPresupuestoCaptura, CicloPresupuesto]:
    captura = db.get(LineaPresupuestoCaptura, linea_captura_id)
    if captura is None:
        raise LookupError("Línea de captura de presupuesto no encontrada")
    ciclo = db.get(CicloPresupuesto, captura.ciclo_id)
    if ciclo is None or ciclo.hotel_id != hotel_id:
        raise LookupError("Línea de captura de presupuesto no encontrada")
    return captura, ciclo


def _reemplazar_lineas_mensuales(
    db: Session, *, linea_captura_id: int, periodos: Sequence[str], importes: Sequence[Decimal]
) -> list[LineaPresupuestoMensual]:
    db.execute(
        delete(LineaPresupuestoMensual).where(
            LineaPresupuestoMensual.linea_captura_id == linea_captura_id
        )
    )
    filas = [
        LineaPresupuestoMensual(linea_captura_id=linea_captura_id, periodo=periodo, importe=importe)
        for periodo, importe in zip(periodos, importes, strict=True)
    ]
    db.add_all(filas)
    db.flush()
    return filas


def prorratear_con_perfil(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    linea_captura_id: int,
    perfil_distribucion_id: int,
) -> list[LineaPresupuestoMensual]:
    captura, ciclo = _captura_y_ciclo(db, hotel_id, linea_captura_id)
    if captura.propuesta_anual is None:
        raise DistribucionInvalida(422, "La línea no tiene una propuesta anual capturada")
    perfil = db.get(PerfilDistribucion, perfil_distribucion_id)
    if perfil is None or (perfil.hotel_id is not None and perfil.hotel_id != hotel_id):
        raise LookupError("Perfil de distribución no encontrado")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    pesos = [Decimal(p) for p in perfil.pesos]
    importes = repartir(captura.propuesta_anual, pesos)
    filas = _reemplazar_lineas_mensuales(
        db, linea_captura_id=captura.id, periodos=periodos, importes=importes
    )
    captura.perfil_distribucion_id = perfil.id
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.linea_prorrateada",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={
            "perfil_distribucion_id": perfil.id,
            "propuesta_anual": str(captura.propuesta_anual),
        },
    )
    return filas


def fijar_importes_mensuales(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    linea_captura_id: int,
    importes: dict[str, Decimal],
) -> list[LineaPresupuestoMensual]:
    captura, ciclo = _captura_y_ciclo(db, hotel_id, linea_captura_id)
    if captura.propuesta_anual is None:
        raise DistribucionInvalida(422, "La línea no tiene una propuesta anual capturada")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    if set(importes) != set(periodos):
        raise DistribucionInvalida(
            422, "Hay que dar un importe para cada uno de los 12 periodos del año fiscal"
        )
    suma = sum(importes.values(), Decimal(0)).quantize(MICRO)
    anual = captura.propuesta_anual.quantize(MICRO)
    if suma != anual:
        raise DistribucionInvalida(
            422,
            f"La suma de los importes mensuales ({suma}) no coincide con la propuesta "
            f"anual ({anual})",
        )
    filas = _reemplazar_lineas_mensuales(
        db, linea_captura_id=captura.id, periodos=periodos, importes=[importes[p] for p in periodos]
    )
    captura.perfil_distribucion_id = None
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.linea_mensualizada_manual",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"propuesta_anual": str(captura.propuesta_anual)},
    )
    return filas
