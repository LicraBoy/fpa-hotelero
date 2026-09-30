"""Cálculo de saldos mensuales por cuenta (en Python con `Decimal`, ver ADR 0002)."""

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import CERO
from fpa.modelos.base import ahora_utc
from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento
from fpa.modelos.saldos import SaldoMensualCuenta

Importe = tuple[str, Decimal, Decimal]  # (cuenta, débito, crédito)
Agregado = tuple[Decimal, Decimal, int]  # (suma débito, suma crédito, n movimientos)


def agregar_por_cuenta(importes: Iterable[Importe]) -> dict[str, Agregado]:
    """Suma débito y crédito por cuenta. Función pura."""
    debitos: dict[str, Decimal] = defaultdict(lambda: CERO)
    creditos: dict[str, Decimal] = defaultdict(lambda: CERO)
    cuentas: dict[str, int] = defaultdict(int)
    for cuenta, debito, credito in importes:
        debitos[cuenta] += debito
        creditos[cuenta] += credito
        cuentas[cuenta] += 1
    return {c: (debitos[c], creditos[c], cuentas[c]) for c in cuentas}


def recalcular_saldos(db: Session, *, hotel_id: int, periodo: str) -> int:
    """Reconstruye los saldos de un hotel y periodo desde su carga **vigente**.

    Es idempotente: se puede llamar cuantas veces se quiera. Si el periodo no tiene carga
    vigente, sus saldos se borran. Devuelve cuántas cuentas quedaron con saldo.
    """
    vigente = db.scalar(
        select(CargaArchivo).where(
            CargaArchivo.hotel_id == hotel_id,
            CargaArchivo.periodo == periodo,
            CargaArchivo.estado == EstadoCarga.VIGENTE.value,
        )
    )
    db.execute(
        delete(SaldoMensualCuenta).where(
            SaldoMensualCuenta.hotel_id == hotel_id, SaldoMensualCuenta.periodo == periodo
        )
    )
    if vigente is None:
        db.flush()
        return 0
    filas = db.execute(
        select(Movimiento.cuenta_codigo, Movimiento.debito, Movimiento.credito).where(
            Movimiento.carga_id == vigente.id, Movimiento.hotel_id == hotel_id
        )
    ).all()
    agregados = agregar_por_cuenta((c, d, h) for c, d, h in filas)
    ahora = ahora_utc()
    if agregados:
        db.execute(
            insert(SaldoMensualCuenta),
            [
                {
                    "hotel_id": hotel_id,
                    "periodo": periodo,
                    "cuenta_codigo": cuenta,
                    "suma_debito": debito,
                    "suma_credito": credito,
                    "n_movimientos": n,
                    "carga_id": vigente.id,
                    "calculado_en": ahora,
                }
                for cuenta, (debito, credito, n) in sorted(agregados.items())
            ],
        )
    db.flush()
    return len(agregados)
