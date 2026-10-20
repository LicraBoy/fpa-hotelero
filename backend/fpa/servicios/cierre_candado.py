"""Candado de los periodos aprobados o bloqueados (Fase 5.4).

Va aparte de `cierre.py` porque lo usan los servicios de carga y de captura, que ese módulo (que
calcula el Variance) no puede importar sin un ciclo.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.cierre import ESTADOS_CERRADOS, CierrePeriodo


class PeriodoCerrado(Exception):
    """Se intentó cambiar datos de un periodo aprobado o bloqueado."""


def periodos_cerrados(db: Session, hotel_id: int) -> dict[str, str]:
    """Meses cuyos datos no pueden cambiar -> periodo cerrado que los protege."""
    protegidos: dict[str, str] = {}
    for cierre in db.scalars(
        select(CierrePeriodo).where(
            CierrePeriodo.hotel_id == hotel_id, CierrePeriodo.estado.in_(ESTADOS_CERRADOS)
        )
    ):
        meses = (cierre.congelado or {}).get("periodos_ytd") or [cierre.periodo]
        for mes in meses:
            protegidos.setdefault(mes, cierre.periodo)
    return protegidos


def exigir_abierto(db: Session, hotel_id: int, periodos: list[str]) -> None:
    """Lanza `PeriodoCerrado` si alguno de los meses está protegido por un cierre."""
    protegidos = periodos_cerrados(db, hotel_id)
    tocados = sorted({p for p in periodos if p in protegidos})
    if tocados:
        cierres = sorted({protegidos[p] for p in tocados})
        raise PeriodoCerrado(
            f"El mes {', '.join(tocados)} pertenece al cierre de {', '.join(cierres)}, que está "
            "aprobado o bloqueado. Para cambiarlo, Contraloría debe reabrir el cierre."
        )
