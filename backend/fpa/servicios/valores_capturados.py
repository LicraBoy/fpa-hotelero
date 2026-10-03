"""Actual **capturado a mano** de las líneas que no salen de los movimientos.

El tipo de cambio de cada mes (`Exchange Rate`) y las asignaciones corporativas que Contraloría
escribe a mano no tienen cuentas: su Actual se captura. Se guarda por mes, con quién lo escribió y
una entrada en la bitácora; capturar de nuevo cambia el valor (queda el rastro en la bitácora) y un
valor en blanco lo borra. Solo se pueden capturar líneas de detalle o informativas **sin cuentas
vinculadas y sin regla de suma**: lo que sale de los movimientos o de un total no se escribe a mano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.plan import ValorCapturado
from fpa.modelos.tipos import MICRO
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.actual import version_de_mapeo
from fpa.servicios.auditoria import auditar
from fpa.servicios.reglas_suma import reglas_como_mapa

IMPORTE_MAXIMO = Decimal("1000000000000")
ORIGEN_MANUAL = "manual"
_RE_PERIODO = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")


class CapturaInvalida(ValueError):
    """Un valor no se puede capturar (línea, mes o importe no válidos)."""


@dataclass(frozen=True)
class ValorEntrada:
    linea_id: int
    periodo: str
    importe: Decimal | None  # None = borrar el valor capturado


def lineas_capturables(db: Session, hotel_id: int, version_mapeo_id: int | None = None) -> set[int]:
    """Ids de las líneas cuyo Actual se puede capturar a mano en la estructura vigente.

    Se calcula contra el mapeo indicado (por omisión, el aprobado): una línea con cuentas vinculadas
    sale de los movimientos y no se captura.
    """
    estructura = RepositorioReporte(db, hotel_id).vigente()
    if estructura is None:
        return set()
    mapeo = version_de_mapeo(db, hotel_id, version_mapeo_id)
    con_cuentas = {v.linea_id for v in RepositorioMapeo(db, hotel_id).vinculos(mapeo.id)}
    con_regla = set(reglas_como_mapa(db, hotel_id, estructura.id))
    return {
        x.id
        for x in RepositorioReporte(db, hotel_id).lineas(estructura.id)
        if x.tipo in ("detalle", "informativa")
        and x.id not in con_cuentas
        and x.id not in con_regla
    }


def capturar_actuales(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    valores: list[ValorEntrada],
) -> int:
    """Guarda (o borra) los Actuales capturados. Devuelve cuántos cambiaron. El llamador hace
    commit.

    Lanza `LookupError` si no hay estructura o mapeo y `CapturaInvalida` ante un valor no válido;
    en ese caso no se guarda **ninguno**.
    """
    estructura = RepositorioReporte(db, hotel_id).vigente()
    if estructura is None:
        raise LookupError("Primero importa la estructura del reporte (reporte/importar)")
    if not valores:
        raise CapturaInvalida("No hay valores que guardar")
    capturables = lineas_capturables(db, hotel_id)
    nombres = {x.id: x.descripcion for x in RepositorioReporte(db, hotel_id).lineas(estructura.id)}

    vistos: set[tuple[int, str]] = set()
    for v in valores:
        nombre = nombres.get(v.linea_id)
        if nombre is None:
            raise CapturaInvalida(f"La línea {v.linea_id} no pertenece al reporte vigente")
        if v.linea_id not in capturables:
            raise CapturaInvalida(
                f"«{nombre.strip()}» sale de cuentas o de un total: su Actual no se captura a mano"
            )
        if not _RE_PERIODO.match(v.periodo):
            raise CapturaInvalida(f"El mes {v.periodo!r} no es válido (AAAA-MM)")
        if v.importe is not None and (not v.importe.is_finite() or abs(v.importe) > IMPORTE_MAXIMO):
            raise CapturaInvalida(f"Importe no válido en «{nombre.strip()}» ({v.periodo})")
        if (v.linea_id, v.periodo) in vistos:
            raise CapturaInvalida(f"«{nombre.strip()}» ({v.periodo}) viene repetido")
        vistos.add((v.linea_id, v.periodo))

    cambios: list[dict[str, str | None]] = []
    with db.begin_nested():
        for v in valores:
            existente = db.scalar(
                select(ValorCapturado).where(
                    ValorCapturado.hotel_id == hotel_id,
                    ValorCapturado.version_estructura_id == estructura.id,
                    ValorCapturado.linea_id == v.linea_id,
                    ValorCapturado.periodo == v.periodo,
                )
            )
            nuevo = None if v.importe is None else v.importe.quantize(MICRO)
            antes = None if existente is None else existente.importe
            if antes == nuevo:
                continue
            if nuevo is None:
                if existente is not None:
                    db.delete(existente)
            elif existente is None:
                db.add(
                    ValorCapturado(
                        hotel_id=hotel_id,
                        version_estructura_id=estructura.id,
                        linea_id=v.linea_id,
                        periodo=v.periodo,
                        importe=nuevo,
                        origen=ORIGEN_MANUAL,
                    )
                )
            else:
                existente.importe = nuevo
                existente.origen = ORIGEN_MANUAL
            cambios.append(
                {
                    "linea": nombres[v.linea_id].strip(),
                    "periodo": v.periodo,
                    "antes": None if antes is None else str(antes),
                    "despues": None if nuevo is None else str(nuevo),
                }
            )
        db.flush()
        if cambios:
            auditar(
                db,
                organizacion_id=organizacion_id,
                hotel_id=hotel_id,
                usuario_id=usuario_id,
                accion="actual.capturado",
                entidad="valor_capturado",
                detalle={"n": len(cambios), "cambios": cambios[:50]},
            )
    return len(cambios)
