"""Drill-down del reporte (Fase 4.2): línea -> cuentas -> movimientos -> asiento.

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin `drilldown:leer` 403. Los
movimientos traen conceptos de proveedores y huéspedes, por eso el permiso es aparte del de ver el
reporte. La primera consulta de movimientos de una cuenta queda en la bitácora (sin su contenido).
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as RutaParam
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_REPORTE
from fpa.api.v1.tipos import IdRuta
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.modelos.cargas import Movimiento
from fpa.servicios.auditoria import auditar
from fpa.servicios.drilldown import (
    LIMITE_MAXIMO,
    CursorInvalido,
    desglose_de_linea,
    movimientos_de_cuenta,
    vista_de_asiento,
)

router = APIRouter(tags=["drilldown"], responses=RESPUESTAS_REPORTE)

PATRON_PERIODO = r"^20\d{2}-(0[1-9]|1[0-2])$"
Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.DRILLDOWN_LEER))]
Periodo = Annotated[str, Query(pattern=PATRON_PERIODO, description="AAAA-MM")]
BloqueConsulta = Annotated[
    Literal["mes", "ytd"], Query(description="mes = solo ese mes; ytd = año fiscal acumulado")
]
CodigoCuenta = Annotated[
    str, RutaParam(min_length=1, max_length=40, pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]*$")
]
CodigoAsiento = Annotated[
    str, RutaParam(min_length=1, max_length=40, pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]*$")
]


class CuentaDesgloseSalida(BaseModel):
    cuenta_codigo: str
    descripcion: str | None
    signo: int
    neto: Decimal
    aporte: Decimal
    n_movimientos: int


class ComponenteSalida(BaseModel):
    linea_id: int
    descripcion: str
    tipo: str
    signo: int
    importe: Decimal


class DesgloseSalida(BaseModel):
    linea_id: int
    descripcion: str
    tipo: str
    periodo: str
    bloque: str
    periodos: list[str]
    cifra: Decimal
    suma: Decimal
    cuadra: bool
    cuentas: list[CuentaDesgloseSalida]
    componentes: list[ComponenteSalida]


class MovimientoSalida(BaseModel):
    id: int
    periodo: str
    fecha: date
    cuenta_codigo: str
    cuenta_descripcion: str
    asiento: str
    tp_asiento: str | None
    concepto: str | None
    debito: Decimal
    credito: Decimal
    neto: Decimal
    cantidad: Decimal | None
    costo: Decimal | None
    fila_origen: int


class ResumenSalida(BaseModel):
    n_movimientos: int
    debito: Decimal
    credito: Decimal
    neto: Decimal


class PaginaSalida(BaseModel):
    cuenta_codigo: str
    descripcion: str | None
    periodo: str
    bloque: str
    periodos: list[str]
    resumen: ResumenSalida
    movimientos: list[MovimientoSalida]
    siguiente_cursor: str | None


class AsientoSalida(BaseModel):
    asiento: str
    periodo: str
    debito: Decimal
    credito: Decimal
    cuadra: bool
    truncado: bool
    movimientos: list[MovimientoSalida]


def _movimiento(m: Movimiento) -> MovimientoSalida:
    return MovimientoSalida(
        id=m.id,
        periodo=m.periodo,
        fecha=m.fecha,
        cuenta_codigo=m.cuenta_codigo,
        cuenta_descripcion=m.cuenta_descripcion,
        asiento=m.asiento,
        tp_asiento=m.tp_asiento,
        concepto=m.concepto,
        debito=m.debito,
        credito=m.credito,
        neto=m.debito - m.credito,
        cantidad=m.cantidad,
        costo=m.costo,
        fila_origen=m.fila_origen,
    )


@router.get(
    "/hoteles/{hotel_id}/variance/lineas/{linea_id}/desglose", response_model=DesgloseSalida
)
def desglose(
    linea_id: IdRuta,
    contexto: Lectura,
    periodo: Periodo,
    bloque: BloqueConsulta = "mes",
    db: Session = Depends(get_db),
) -> DesgloseSalida:
    """Qué hay detrás de la cifra de una línea: sus cuentas, o los componentes de un total."""
    try:
        d = desglose_de_linea(
            db, hotel_id=contexto.hotel_id, periodo=periodo, linea_id=linea_id, bloque=bloque
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    return DesgloseSalida(
        linea_id=d.linea_id,
        descripcion=d.descripcion,
        tipo=d.tipo,
        periodo=d.periodo,
        bloque=d.bloque,
        periodos=d.periodos,
        cifra=d.cifra,
        suma=d.suma,
        cuadra=d.cuadra,
        cuentas=[CuentaDesgloseSalida(**vars(c)) for c in d.cuentas],
        componentes=[ComponenteSalida(**vars(c)) for c in d.componentes],
    )


@router.get(
    "/hoteles/{hotel_id}/variance/cuentas/{cuenta_codigo}/movimientos",
    response_model=PaginaSalida,
    responses={422: {"description": "Cursor inválido, periodo o límite fuera de rango"}},
)
def movimientos(
    cuenta_codigo: CodigoCuenta,
    contexto: Lectura,
    periodo: Periodo,
    bloque: BloqueConsulta = "mes",
    cursor: Annotated[
        str | None, Query(max_length=200, description="`siguiente_cursor` de la página anterior")
    ] = None,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = 50,
    db: Session = Depends(get_db),
) -> PaginaSalida:
    """Movimientos de una cuenta, paginados por cursor (keyset, nunca OFFSET)."""
    try:
        p = movimientos_de_cuenta(
            db,
            hotel_id=contexto.hotel_id,
            periodo=periodo,
            bloque=bloque,
            cuenta_codigo=cuenta_codigo,
            cursor=cursor,
            limite=limite,
        )
    except CursorInvalido as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    if cursor is None:
        auditar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            accion="drilldown.consultado",
            entidad="cuenta",
            detalle={
                "cuenta": cuenta_codigo,
                "periodo": periodo,
                "bloque": bloque,
                "n_movimientos": p.resumen.n_movimientos,
            },
        )
        db.commit()
    return PaginaSalida(
        cuenta_codigo=p.cuenta_codigo,
        descripcion=p.descripcion,
        periodo=p.periodo,
        bloque=p.bloque,
        periodos=p.periodos,
        resumen=ResumenSalida(
            n_movimientos=p.resumen.n_movimientos,
            debito=p.resumen.debito,
            credito=p.resumen.credito,
            neto=p.resumen.neto,
        ),
        movimientos=[_movimiento(m) for m in p.movimientos],
        siguiente_cursor=p.siguiente_cursor,
    )


@router.get("/hoteles/{hotel_id}/asientos/{asiento}", response_model=AsientoSalida)
def asiento(
    asiento: CodigoAsiento,
    contexto: Lectura,
    periodo: Periodo,
    db: Session = Depends(get_db),
) -> AsientoSalida:
    """Todas las líneas de un asiento en el periodo, con sus totales de Débito y Crédito."""
    v = vista_de_asiento(db, hotel_id=contexto.hotel_id, periodo=periodo, asiento=asiento)
    if not v.movimientos:
        raise HTTPException(status_code=404, detail="Asiento no encontrado en ese periodo")
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="drilldown.consultado",
        entidad="asiento",
        detalle={"asiento": asiento, "periodo": periodo, "n_movimientos": len(v.movimientos)},
    )
    db.commit()
    return AsientoSalida(
        asiento=v.asiento,
        periodo=v.periodo,
        debito=v.debito,
        credito=v.credito,
        cuadra=v.cuadra,
        truncado=v.truncado,
        movimientos=[_movimiento(m) for m in v.movimientos],
    )
