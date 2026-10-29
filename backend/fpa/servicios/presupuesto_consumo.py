"""Cuentas de consumo del Budget: Diesel, Gas, Electricity y Water & Sewer.

La hoja de detalle de estas cuentas no lista partidas: trae, mes a mes, **unidades** (litros, kWh, m³),
**costo unitario** y **total** de cuatro bloques (`BLOQUES_CONSUMO`): Real del año previo, Budget previo,
Est-Act y Budget. Aquí se guardan los cuatro completos (`ConsumoLineaMes`); solo el bloque `budget` se
edita (unidades y costo unitario de cada mes) y es el que sustenta el Budget de la cuenta:

    Budget del mes = total de consumo del mes  (+ distribución de partidas × (1 + inflación), si la
                                                 cuenta también tiene partidas: *Water & Sewer*)

La inflación de la hoja de consumo del Excel no se aplica al consumo (el costo unitario ya es la tarifa
del año): así cuadran los totales del libro. Igual que con partidas, el Budget calculado se escribe como
detalle `fijo` (`guardar_detalle(..., desde_partidas=True)`) y la edición mes a mes queda bloqueada.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fpa.modelos.presupuesto import (
    BLOQUES_CONSUMO,
    ConsumoLineaMes,
    InflacionLineaMes,
    LineaPresupuestoCaptura,
)
from fpa.modelos.tipos import MICRO
from fpa.servicios.auditoria import auditar
from fpa.servicios.presupuesto_detalle import CeldaDetalle, DetalleInvalido, _captura_de, guardar_detalle
from fpa.servicios.presupuesto_distribucion import periodos_de_ano_fiscal

_CERO = Decimal(0)
MAX_UNIDADES = Decimal("1000000000000")
MAX_COSTO = Decimal("1000000000")

Mes = tuple[Decimal | None, Decimal | None, Decimal | None]  # (unidades, costo unitario, total)


@dataclass(frozen=True)
class ConsumoHoja:
    unidad: str
    bloques: dict[str, list[Mes]]


def consumo_budget(db: Session, captura_id: int, periodos: Sequence[str]) -> list[Decimal]:
    """Total del bloque Budget por mes (ceros si la cuenta no es de consumo)."""
    filas = {
        f.periodo: f.total
        for f in db.scalars(
            select(ConsumoLineaMes).where(
                ConsumoLineaMes.linea_captura_id == captura_id, ConsumoLineaMes.bloque == "budget"
            )
        )
    }
    return [filas.get(p) or _CERO for p in periodos]


def leer_consumo(db: Session, captura: LineaPresupuestoCaptura, periodos: Sequence[str]) -> ConsumoHoja | None:
    if not captura.usa_consumo:
        return None
    por: dict[tuple[str, str], ConsumoLineaMes] = {
        (f.bloque, f.periodo): f
        for f in db.scalars(
            select(ConsumoLineaMes).where(ConsumoLineaMes.linea_captura_id == captura.id)
        )
    }
    bloques: dict[str, list[Mes]] = {}
    for b in BLOQUES_CONSUMO:
        meses: list[Mes] = []
        for p in periodos:
            f = por.get((b, p))
            meses.append((f.unidades, f.costo_unitario, f.total) if f else (None, None, None))
        bloques[b] = meses
    return ConsumoHoja(captura.unidad_consumo or "", bloques)


def _recalcular_budget(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    captura: LineaPresupuestoCaptura,
    periodos: Sequence[str],
    visibles: set[int] | None,
) -> None:
    """Escribe el Budget de la cuenta: consumo + (partidas × (1 + inflación)) si las hay."""
    from fpa.servicios.presupuesto_partidas import (  # noqa: PLC0415 (evita el ciclo de imports)
        _partidas_guardadas,
        budget_mensual,
        distribucion_de,
    )

    if captura.usa_partidas:
        tasas = {
            t.periodo: t.tasa
            for t in db.scalars(
                select(InflacionLineaMes).where(InflacionLineaMes.linea_captura_id == captura.id)
            )
        }
        partidas = budget_mensual(
            distribucion_de(_partidas_guardadas(db, captura.id, periodos)),
            [tasas.get(p) for p in periodos],
        )
    else:
        partidas = [_CERO] * len(periodos)
    consumo = consumo_budget(db, captura.id, periodos) if captura.usa_consumo else [_CERO] * len(periodos)
    guardar_detalle(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        linea_id=linea_id,
        celdas=[
            CeldaDetalle(periodo=p, metodo="fijo", monto_fijo=a + b)
            for p, a, b in zip(periodos, partidas, consumo, strict=True)
        ],
        visibles=visibles,
        desde_partidas=True,
    )


def guardar_consumo_importado(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    unidad: str,
    bloques: Mapping[str, Sequence[Mes]],
    visibles: set[int] | None,
) -> None:
    """Guarda los 4 bloques de la hoja de consumo del Excel (reemplaza los que había) y deja la cuenta
    mensualizada con su Budget."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    if set(bloques) != set(BLOQUES_CONSUMO) or any(len(m) != len(periodos) for m in bloques.values()):
        raise DetalleInvalido(422, "El consumo debe traer los 4 bloques de 12 meses")
    db.execute(delete(ConsumoLineaMes).where(ConsumoLineaMes.linea_captura_id == captura.id))
    for b in BLOQUES_CONSUMO:
        for p, (u, c, t) in zip(periodos, bloques[b], strict=True):
            db.add(
                ConsumoLineaMes(
                    linea_captura_id=captura.id, periodo=p, bloque=b, unidades=u, costo_unitario=c, total=t
                )
            )
    captura.usa_consumo = True
    captura.unidad_consumo = unidad[:10]
    db.flush()
    _recalcular_budget(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        linea_id=linea_id,
        captura=captura,
        periodos=periodos,
        visibles=visibles,
    )
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.consumo_guardado",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id, "origen": "excel", "unidad": captura.unidad_consumo},
    )


def editar_consumo_budget(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    cambios: Mapping[str, tuple[Decimal, Decimal]],
    visibles: set[int] | None,
) -> None:
    """Cambia unidades y costo unitario de los meses indicados del bloque Budget (`periodo` → (unidades,
    costo)); el total de cada uno es unidades × costo y los demás meses no se tocan."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    if not captura.usa_consumo:
        raise DetalleInvalido(409, "La cuenta no se captura por consumo")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    if not cambios or any(p not in periodos for p in cambios):
        raise DetalleInvalido(422, "Los meses a cambiar deben ser periodos del año fiscal")
    for u, c in cambios.values():
        if u < 0 or c < 0 or u > MAX_UNIDADES or c > MAX_COSTO:
            raise DetalleInvalido(422, "Las unidades y el costo unitario no pueden ser negativos")
    filas = {
        f.periodo: f
        for f in db.scalars(
            select(ConsumoLineaMes).where(
                ConsumoLineaMes.linea_captura_id == captura.id, ConsumoLineaMes.bloque == "budget"
            )
        )
    }
    for p, (u, c) in cambios.items():
        fila = filas.get(p)
        if fila is None:
            fila = ConsumoLineaMes(linea_captura_id=captura.id, periodo=p, bloque="budget")
            db.add(fila)
        fila.unidades = u.quantize(MICRO)
        fila.costo_unitario = c.quantize(MICRO)
        fila.total = (u * c).quantize(MICRO)
    db.flush()
    _recalcular_budget(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        linea_id=linea_id,
        captura=captura,
        periodos=periodos,
        visibles=visibles,
    )
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.consumo_editado",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id, "meses": sorted(cambios), "propuesta_anual": str(captura.propuesta_anual)},
    )


def quitar_consumo(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    visibles: set[int] | None,
) -> None:
    """Vuelve la cuenta al Editor mensual: se borra el consumo y el Budget que tenía queda como detalle
    `fijo` (si también tiene partidas, el Budget pasa a ser solo el de las partidas)."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    db.execute(delete(ConsumoLineaMes).where(ConsumoLineaMes.linea_captura_id == captura.id))
    captura.usa_consumo = False
    captura.unidad_consumo = None
    db.flush()
    if captura.usa_partidas:
        _recalcular_budget(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            captura=captura,
            periodos=periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id),
            visibles=visibles,
        )
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.consumo_quitado",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id},
    )
