"""Persistencia de cargas: un archivo leído -> una carga por periodo + sus movimientos."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import CERO, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento


class CargaInvalida(ValueError):
    """El resultado de la lectura no puede guardarse."""


@dataclass(frozen=True)
class DatosArchivo:
    nombre: str
    sha256: str
    tamano_bytes: int | None = None


def _fila_movimiento(m: MovimientoLeido, carga_id: int, hotel_id: int) -> dict[str, Any]:
    return {
        "carga_id": carga_id,
        "hotel_id": hotel_id,
        "periodo": m.periodo,
        "cuenta_codigo": m.cuenta_codigo,
        "cuenta_descripcion": m.cuenta_descripcion,
        "fecha": m.fecha,
        "asiento": m.asiento,
        "tp_asiento": m.tp_asiento,
        "operacion": m.operacion,
        "tp_doc": m.tp_doc,
        "numero": m.numero,
        "concepto": m.concepto,
        "debito": m.debito,
        "credito": m.credito,
        "saldo": m.saldo,
        "cantidad": m.cantidad,
        "costo": m.costo,
        "fila_origen": m.fila,
    }


def registrar_carga(
    db: Session,
    *,
    hotel_id: int,
    usuario_id: int | None,
    resultado: ResultadoLectura,
    archivo: DatosArchivo,
    controles: dict[str, Any] | None = None,
) -> list[CargaArchivo]:
    """Guarda una carga vigente por cada periodo del archivo, **todo o nada**.

    Se ejecuta dentro de un SAVEPOINT: si algo falla a la mitad, no queda ninguna carga ni
    movimiento. El llamador decide cuándo confirmar (`commit`) la transacción completa.
    Las reglas de idempotencia y reemplazo se aplican antes, en `cargar_archivo` (sub-fase 1.4).
    """
    if resultado.fuente is None:
        raise CargaInvalida("La lectura no indica su fuente")
    if not resultado.movimientos:
        raise CargaInvalida("El archivo no trae movimientos")
    if not resultado.es_valido:
        raise CargaInvalida(
            "La lectura tiene errores; no se guarda: " + "; ".join(resultado.errores[:3])
        )

    por_periodo: dict[str, list[MovimientoLeido]] = defaultdict(list)
    for m in resultado.movimientos:
        por_periodo[m.periodo].append(m)

    cargas: list[CargaArchivo] = []
    with db.begin_nested():
        for periodo in sorted(por_periodo):
            movs = por_periodo[periodo]
            total_debito: Decimal = sum((m.debito for m in movs), CERO)
            total_credito: Decimal = sum((m.credito for m in movs), CERO)
            carga = CargaArchivo(
                hotel_id=hotel_id,
                fuente=resultado.fuente.value,
                nombre_archivo=archivo.nombre[:255],
                sha256=archivo.sha256,
                tamano_bytes=archivo.tamano_bytes,
                periodo=periodo,
                fecha_min=min(m.fecha for m in movs),
                fecha_max=max(m.fecha for m in movs),
                n_movimientos=len(movs),
                total_debito=total_debito,
                total_credito=total_credito,
                estado=EstadoCarga.VIGENTE.value,
                controles=controles,
                usuario_id=usuario_id,
            )
            db.add(carga)
            db.flush()
            db.execute(insert(Movimiento), [_fila_movimiento(m, carga.id, hotel_id) for m in movs])
            cargas.append(carga)
    return cargas
