"""Validación del mapeo contra los movimientos reales de un periodo.

Responde, para una versión de mapeo y un periodo (`AAAA-MM`):
- **sin_mapear**: cuentas de resultados (clases 4, 5 y 6) con movimiento neto distinto de cero que
  ninguna línea toma. Es el único hallazgo *bloqueante*: aprobar un mapeo así dejaría fuera dinero.
- **en_varias_lineas**: cuentas que alimentan más de una línea. Es legítimo (el Excel lo hace), solo
  se informa.
- **sin_catalogo**: vínculos a cuentas que no están en el catálogo del hotel.
- **discrepancias_signo**: signo del vínculo distinto de la naturaleza de la cuenta (TIPO).
- **lineas_sin_cuentas**: líneas de detalle que no tienen ninguna cuenta (siempre darán cero).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.reporte import LineaReporte
from fpa.modelos.saldos import SaldoMensualCuenta
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.mapeo import discrepancias_de_signo

CLASES_DE_RESULTADOS = frozenset("456")
CERO = Decimal("0")


@dataclass(frozen=True)
class CuentaSinMapear:
    cuenta_codigo: str
    descripcion: str | None
    neto: Decimal


@dataclass
class ReporteMapeo:
    version_mapeo_id: int
    periodo: str
    cuentas_con_movimiento: int = 0
    cuentas_mapeadas: int = 0
    sin_mapear: list[CuentaSinMapear] = field(default_factory=list)
    en_varias_lineas: dict[str, list[int]] = field(default_factory=dict)
    sin_catalogo: list[str] = field(default_factory=list)
    discrepancias_signo: list[dict[str, Any]] = field(default_factory=list)
    lineas_sin_cuentas: list[int] = field(default_factory=list)
    # Cuentas con movimiento que se dejaron fuera a propósito (con motivo registrado)
    excluidas_con_movimiento: list[str] = field(default_factory=list)

    @property
    def bloqueantes(self) -> list[str]:
        """Motivos por los que un mapeo no se puede aprobar."""
        if not self.sin_mapear:
            return []
        total = sum((abs(c.neto) for c in self.sin_mapear), CERO)
        return [
            f"{len(self.sin_mapear)} cuentas con movimiento en {self.periodo} no están mapeadas "
            f"(importe absoluto {total})"
        ]

    @property
    def aprobable(self) -> bool:
        return not self.bloqueantes

    def a_dict(self) -> dict[str, Any]:
        return {
            "version_mapeo_id": self.version_mapeo_id,
            "periodo": self.periodo,
            "aprobable": self.aprobable,
            "bloqueantes": self.bloqueantes,
            "cuentas_con_movimiento": self.cuentas_con_movimiento,
            "cuentas_mapeadas": self.cuentas_mapeadas,
            "sin_mapear": [
                {
                    "cuenta_codigo": c.cuenta_codigo,
                    "descripcion": c.descripcion,
                    "neto": str(c.neto),
                }
                for c in self.sin_mapear
            ],
            "en_varias_lineas": self.en_varias_lineas,
            "sin_catalogo": self.sin_catalogo,
            "discrepancias_signo": self.discrepancias_signo,
            "lineas_sin_cuentas": self.lineas_sin_cuentas,
            "excluidas_con_movimiento": self.excluidas_con_movimiento,
        }


def validar_mapeo(
    db: Session, *, hotel_id: int, version_mapeo_id: int, periodo: str
) -> ReporteMapeo:
    """Función de lectura: no modifica nada. Lanza `LookupError` si la versión no es del hotel."""
    repo = RepositorioMapeo(db, hotel_id)
    version = repo.obtener(version_mapeo_id)
    if version is None:
        raise LookupError("Versión de mapeo no encontrada")
    vinculos = repo.vinculos(version.id)
    por_cuenta: dict[str, set[int]] = {}
    for v in vinculos:
        por_cuenta.setdefault(v.cuenta_codigo, set()).add(v.linea_id)

    reporte = ReporteMapeo(version_mapeo_id=version.id, periodo=periodo)
    reporte.cuentas_mapeadas = len(por_cuenta)

    saldos = db.scalars(
        select(SaldoMensualCuenta).where(
            SaldoMensualCuenta.hotel_id == hotel_id, SaldoMensualCuenta.periodo == periodo
        )
    ).all()
    catalogo = {c.codigo: c for c in RepositorioCatalogo(db, hotel_id).todas()}
    excluidas = {e.cuenta_codigo for e in repo.excluidas(version.id)}
    for saldo in sorted(saldos, key=lambda s: s.cuenta_codigo):
        if saldo.cuenta_codigo[:1] not in CLASES_DE_RESULTADOS:
            continue
        reporte.cuentas_con_movimiento += 1
        if saldo.neto != CERO and saldo.cuenta_codigo in excluidas:
            reporte.excluidas_con_movimiento.append(saldo.cuenta_codigo)
        elif saldo.neto != CERO and saldo.cuenta_codigo not in por_cuenta:
            cuenta = catalogo.get(saldo.cuenta_codigo)
            reporte.sin_mapear.append(
                CuentaSinMapear(
                    saldo.cuenta_codigo, cuenta.descripcion if cuenta else None, saldo.neto
                )
            )

    reporte.en_varias_lineas = {
        c: sorted(lineas) for c, lineas in sorted(por_cuenta.items()) if len(lineas) > 1
    }
    reporte.sin_catalogo = sorted(c for c in por_cuenta if c not in catalogo)
    reporte.discrepancias_signo = [
        {
            "cuenta_codigo": d.cuenta_codigo,
            "linea_id": d.linea_id,
            "signo_mapeo": d.signo_mapeo,
            "signo_esperado": d.signo_esperado,
            "tipo": d.tipo,
        }
        for d in discrepancias_de_signo(db, hotel_id, version.id)
    ]
    con_cuentas = {v.linea_id for v in vinculos}
    lineas: list[LineaReporte] = RepositorioReporte(db, hotel_id).lineas(
        version.version_estructura_id
    )
    reporte.lineas_sin_cuentas = [
        x.id for x in lineas if x.tipo == "detalle" and x.id not in con_cuentas
    ]
    return reporte
