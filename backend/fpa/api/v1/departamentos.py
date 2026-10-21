"""Importes del Variance por departamento de la cuenta (solo lectura).

Reglas de acceso: sin sesión 401; hotel ajeno 404; sin `variance:leer` 403. El detalle de cuentas
solo viaja con `drilldown:leer`. Quien tiene el acceso limitado a sus secciones recibe 403: un
departamento cruza secciones del reporte. Un periodo Aprobado o Bloqueado se calcula con el mapeo
congelado en su cierre.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_REPORTE
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.servicios.acceso_secciones import exigir_acceso_completo
from fpa.servicios.cierre import versiones_congeladas
from fpa.servicios.departamentos import (
    TIPOS,
    FilaDepartamento,
    Importes,
    importes_por_departamento,
)

router = APIRouter(tags=["variance"], responses=RESPUESTAS_REPORTE)
Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.VARIANCE_LEER))]
CENTAVO = Decimal("0.01")


class ImportesSalida(BaseModel):
    mes: Decimal
    ytd: Decimal


class CuentaSalida(BaseModel):
    codigo: str
    descripcion: str | None
    tipo: str
    mes: Decimal
    ytd: Decimal
    n_lineas: int


class DepartamentoSalida(BaseModel):
    # None = «Sin departamento»
    departamento: str | None
    por_tipo: dict[str, ImportesSalida]
    ingreso: ImportesSalida
    gasto: ImportesSalida
    resultado: ImportesSalida  # ingreso − gasto
    n_cuentas: int
    # Vacío si el rol no tiene `drilldown:leer`
    cuentas: list[CuentaSalida]


class DepartamentosSalida(BaseModel):
    periodo: str
    version_mapeo_id: int
    periodos_ytd: list[str]
    periodos_sin_datos: list[str]
    tipos: list[str]
    cuentas_vinculadas: int
    cuentas_sin_departamento: int
    cuentas_sin_tipo: int
    departamentos: list[DepartamentoSalida]
    total: DepartamentoSalida
    detalle_de_cuentas: bool


def _d(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _imp(e: Importes) -> ImportesSalida:
    return ImportesSalida(mes=_d(e.mes), ytd=_d(e.ytd))


def _fila(f: FilaDepartamento, con_cuentas: bool) -> DepartamentoSalida:
    ing, gas = f.ingreso, f.gasto
    return DepartamentoSalida(
        departamento=f.departamento,
        por_tipo={t: _imp(f.por_tipo[t]) for t in TIPOS if t in f.por_tipo},
        ingreso=_imp(ing),
        gasto=_imp(gas),
        resultado=ImportesSalida(mes=_d(ing.mes - gas.mes), ytd=_d(ing.ytd - gas.ytd)),
        n_cuentas=len(f.cuentas),
        cuentas=(
            [
                CuentaSalida(
                    codigo=c.codigo,
                    descripcion=c.descripcion,
                    tipo=c.tipo,
                    mes=_d(c.mes),
                    ytd=_d(c.ytd),
                    n_lineas=c.n_lineas,
                )
                for c in sorted(f.cuentas.values(), key=lambda c: c.codigo)
            ]
            if con_cuentas
            else []
        ),
    )


@router.get(
    "/hoteles/{hotel_id}/variance/departamentos",
    response_model=DepartamentosSalida,
    responses={**RESPUESTAS_REPORTE, 403: {"description": "Sin permiso o acceso limitado"}},
)
def por_departamento(
    contexto: Lectura,
    periodo: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", description="AAAA-MM")],
    db: Session = Depends(get_db),
) -> DepartamentosSalida:
    exigir_acceso_completo(contexto)
    congeladas = versiones_congeladas(db, contexto.hotel_id, periodo)
    try:
        r = importes_por_departamento(
            db,
            hotel_id=contexto.hotel_id,
            periodo=periodo,
            version_mapeo_id=congeladas[0] if congeladas else None,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    con_cuentas = contexto.principal.puede(contexto.hotel_id, Permiso.DRILLDOWN_LEER)
    total = FilaDepartamento("Total")
    for f in r.filas:
        for tipo, imp in f.por_tipo.items():
            total.importes(tipo).sumar(imp.mes, imp.ytd)
    return DepartamentosSalida(
        periodo=r.periodo,
        version_mapeo_id=r.version_mapeo_id,
        periodos_ytd=r.periodos_ytd,
        periodos_sin_datos=r.periodos_sin_datos,
        tipos=list(TIPOS),
        cuentas_vinculadas=r.cuentas_vinculadas,
        cuentas_sin_departamento=r.cuentas_sin_departamento,
        cuentas_sin_tipo=r.cuentas_sin_tipo,
        departamentos=[_fila(f, con_cuentas) for f in r.filas],
        total=_fila(total, False).model_copy(
            update={"n_cuentas": sum(len(f.cuentas) for f in r.filas), "departamento": None}
        ),
        detalle_de_cuentas=con_cuentas,
    )
