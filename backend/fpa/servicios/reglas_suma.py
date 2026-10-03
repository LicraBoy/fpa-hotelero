"""Reglas de suma del reporte: importarlas y evaluarlas.

El cálculo (`evaluar_totales`) vive en `fpa.calculo.totales` y se re-exporta aquí.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from fpa.calculo.totales import CicloEnReglas, Coeficiente, evaluar_totales
from fpa.ingesta.variance_reglas import ResultadoReglas
from fpa.modelos.reporte import LineaReporte, ReglaSumaLinea, VersionEstructuraReporte
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar

__all__ = [
    "CicloEnReglas",
    "evaluar_totales",
    "importar_reglas_suma",
    "lineas_aditivas",
    "reglas_como_mapa",
]


def importar_reglas_suma(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version: VersionEstructuraReporte,
    leidas: ResultadoReglas,
) -> int:
    """Reemplaza las reglas de la versión de estructura. Devuelve cuántas reglas quedaron."""
    if version.hotel_id != hotel_id:
        raise ValueError("La versión no pertenece al hotel")
    lineas = RepositorioReporte(db, hotel_id).lineas(version.id)
    por_orden: dict[int, LineaReporte] = {x.orden: x for x in lineas}
    with db.begin_nested():
        db.execute(
            delete(ReglaSumaLinea).where(
                ReglaSumaLinea.version_id == version.id, ReglaSumaLinea.hotel_id == hotel_id
            )
        )
        for regla in leidas.reglas:
            destino = por_orden[regla.orden]
            for orden_componente, signo in regla.componentes:
                db.add(
                    ReglaSumaLinea(
                        version_id=version.id,
                        hotel_id=hotel_id,
                        linea_id=destino.id,
                        componente_id=por_orden[orden_componente].id,
                        signo=Decimal(signo),
                    )
                )
        db.flush()
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion="reglas_suma.importadas",
            entidad="estructura_reporte",
            entidad_id=version.id,
            detalle={"n_reglas": len(leidas.reglas), "avisos": leidas.avisos[:10]},
        )
    return len(leidas.reglas)


def _coeficiente(valor: Decimal) -> Coeficiente:
    """±1 como entero (así los importes no ganan decimales); otro factor (0.16) como Decimal."""
    return int(valor) if valor == valor.to_integral_value() else valor


def reglas_como_mapa(
    db: Session, hotel_id: int, version_id: int
) -> dict[int, list[tuple[int, Coeficiente]]]:
    """Reglas guardadas como `linea_id -> [(componente_id, coeficiente)]` para `evaluar_totales`."""
    mapa: dict[int, list[tuple[int, Coeficiente]]] = {}
    for r in RepositorioReporte(db, hotel_id).reglas(version_id):
        mapa.setdefault(r.linea_id, []).append((r.componente_id, _coeficiente(r.signo)))
    return mapa


def lineas_aditivas(
    reglas: Mapping[int, Sequence[tuple[int, Coeficiente]]], lineas_con_cuentas: set[int]
) -> frozenset[int]:
    """Líneas con regla **y** cuentas vinculadas: su valor es «cuentas + componentes»."""
    return frozenset(linea for linea in reglas if linea in lineas_con_cuentas)
