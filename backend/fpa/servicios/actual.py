"""Actual de un periodo, leído de los saldos mensuales y del mapeo."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from fpa.calculo.actual import calcular_actual
from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, periodos_ytd
from fpa.calculo.ytd import AcumuladoYtd, acumular_ytd
from fpa.modelos.mapeo import VersionMapeo
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.saldos import RepositorioSaldos


def version_de_mapeo(db: Session, hotel_id: int, version_mapeo_id: int | None) -> VersionMapeo:
    """La versión pedida o, por omisión, la aprobada vigente. `LookupError` si no hay."""
    repo = RepositorioMapeo(db, hotel_id)
    version = repo.obtener(version_mapeo_id) if version_mapeo_id else repo.aprobada()
    if version is None:
        raise LookupError(
            "Versión de mapeo no encontrada"
            if version_mapeo_id
            else "No hay un mapeo aprobado; indica una versión o aprueba un borrador"
        )
    return version


def netos_del_periodo(db: Session, hotel_id: int, periodo: str) -> dict[str, Decimal]:
    """`neto = Débito − Crédito` por cuenta, de la carga vigente del periodo."""
    return {s.cuenta_codigo: s.neto for s in RepositorioSaldos(db, hotel_id).del_periodo(periodo)}


def actual_del_periodo(
    db: Session, *, hotel_id: int, periodo: str, version_mapeo_id: int | None = None
) -> dict[int, Decimal]:
    version = version_de_mapeo(db, hotel_id, version_mapeo_id)
    vinculos = [
        (v.linea_id, v.cuenta_codigo, v.signo)
        for v in RepositorioMapeo(db, hotel_id).vinculos(version.id)
    ]
    return calcular_actual(vinculos, netos_del_periodo(db, hotel_id, periodo))


def actual_ytd_del_periodo(
    db: Session,
    *,
    hotel_id: int,
    periodo: str,
    version_mapeo_id: int | None = None,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> AcumuladoYtd:
    """Actual acumulado del año fiscal hasta `periodo` (los meses sin carga se informan)."""
    con_datos = set(RepositorioSaldos(db, hotel_id).periodos())
    por_periodo = {
        p: actual_del_periodo(db, hotel_id=hotel_id, periodo=p, version_mapeo_id=version_mapeo_id)
        for p in periodos_ytd(periodo, mes_inicio)
        if p in con_datos
    }
    return acumular_ytd(por_periodo, periodo, mes_inicio)
