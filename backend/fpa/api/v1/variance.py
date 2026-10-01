"""Variance de un periodo (Fase 3.6): Actual, Budget, Variance y Variance % por línea.

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Solo lectura.
Los importes salen redondeados a centavos y los porcentajes a 6 decimales; el cálculo interno es
exacto (el redondeo es solo de presentación).
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.calculo.motor import Cifras
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.servicios.variance import PlanIncompatible, calcular_variance

router = APIRouter(tags=["variance"])
_RE_PERIODO = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
CENTAVO = Decimal("0.01")
MICRO = Decimal("0.000001")

Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.VARIANCE_LEER))]


class CifrasSalida(BaseModel):
    actual: Decimal
    budget: Decimal | None
    var: Decimal | None
    pct: Decimal | None


class LineaVarianceSalida(BaseModel):
    linea_id: int
    orden: int
    tipo: str
    nivel: int
    seccion_id: int | None
    codigo_corporativo: str | None
    descripcion: str
    convencion: str
    mes: CifrasSalida
    ytd: CifrasSalida
    anual: CifrasSalida


class VarianceSalida(BaseModel):
    periodo: str
    ano_fiscal: str
    version_mapeo_id: int
    version_plan_id: int | None
    periodos_ytd: list[str]
    periodos_sin_datos: list[str]
    advertencias: list[str]
    lineas: list[LineaVarianceSalida]


def _cifras(c: Cifras) -> CifrasSalida:
    def dinero(v: Decimal | None) -> Decimal | None:
        return None if v is None else v.quantize(CENTAVO, rounding=ROUND_HALF_UP)

    return CifrasSalida(
        actual=c.actual.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        budget=dinero(c.budget),
        var=dinero(c.var),
        pct=None if c.pct is None else c.pct.quantize(MICRO, rounding=ROUND_HALF_UP),
    )


@router.get("/hoteles/{hotel_id}/variance", response_model=VarianceSalida)
def variance(
    contexto: Lectura,
    periodo: Annotated[str, Query(description="AAAA-MM")],
    version_mapeo_id: Annotated[int | None, Query()] = None,
    version_plan_id: Annotated[int | None, Query()] = None,
    db: Session = Depends(get_db),
) -> VarianceSalida:
    """Variance del periodo con el mapeo aprobado y el Budget vigente (o las indicadas)."""
    if not _RE_PERIODO.match(periodo):
        raise HTTPException(status_code=422, detail="El periodo debe ser AAAA-MM")
    try:
        r = calcular_variance(
            db,
            hotel_id=contexto.hotel_id,
            periodo=periodo,
            version_mapeo_id=version_mapeo_id,
            version_plan_id=version_plan_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except PlanIncompatible as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return VarianceSalida(
        periodo=r.periodo,
        ano_fiscal=r.ano_fiscal,
        version_mapeo_id=r.version_mapeo_id,
        version_plan_id=r.version_plan_id,
        periodos_ytd=r.periodos_ytd,
        periodos_sin_datos=r.periodos_sin_datos,
        advertencias=r.advertencias,
        lineas=[
            LineaVarianceSalida(
                linea_id=x.id,
                orden=x.orden,
                tipo=x.tipo,
                nivel=x.nivel,
                seccion_id=x.seccion_id,
                codigo_corporativo=x.codigo_corporativo,
                descripcion=x.descripcion,
                convencion=r.resultado[x.id].convencion.value,
                mes=_cifras(r.resultado[x.id].mes),
                ytd=_cifras(r.resultado[x.id].ytd),
                anual=_cifras(r.resultado[x.id].anual),
            )
            for x in r.lineas
        ],
    )
