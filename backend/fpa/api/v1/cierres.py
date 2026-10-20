"""Cierre de periodos del Variance (Fase 5.4): estado, historial y cambios de estado.

Reglas de acceso: leer exige `cierre:leer`; cada cambio exige el permiso de esa transición
(revisar, aprobar o bloquear). Una transición que no existe responde 409; sin permiso, 403.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import FechaHoraUtc
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.modelos.cierre import CierrePeriodo
from fpa.modelos.comentarios import ComentarioLinea
from fpa.modelos.identidad import Usuario
from fpa.servicios.cierre import (
    TRANSICIONES,
    CierreInvalido,
    cierre_de,
    historial,
    transicionar,
)

router = APIRouter(tags=["cierres"], responses=RESPUESTAS_HOTEL)

Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CIERRE_LEER))]
PeriodoRuta = Annotated[str, Path(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")]


class TransicionPosible(BaseModel):
    hacia: str
    etiqueta: str
    pide_nota: bool


class TransicionSalida(BaseModel):
    desde: str
    hacia: str
    usuario: str
    nota: str | None
    creado_en: FechaHoraUtc


class CierreSalida(BaseModel):
    periodo: str
    estado: str
    transiciones_posibles: list[TransicionPosible]
    historial: list[TransicionSalida]
    version_mapeo_id: int | None
    version_plan_id: int | None
    version_estructura_id: int | None
    huella_cifras: str | None
    congelado: dict[str, Any] | None
    comentarios_pendientes: int


class ResumenCierre(BaseModel):
    periodo: str
    estado: str


class CambioEstado(BaseModel):
    hacia: str = Field(min_length=1, max_length=12)
    nota: str | None = Field(default=None, max_length=1000)


def _salida(db: Session, contexto: ContextoHotel, periodo: str) -> CierreSalida:
    cierre = cierre_de(db, contexto.hotel_id, periodo)
    estado = cierre.estado if cierre else "borrador"
    puede = contexto.principal.puede
    pasos = [
        TransicionPosible(hacia=t.hacia, etiqueta=t.etiqueta, pide_nota=t.pide_nota)
        for t in TRANSICIONES
        if t.desde == estado and puede(contexto.hotel_id, t.permiso)
    ]
    movimientos = historial(db, cierre)
    nombres = {
        u.id: u.nombre
        for u in db.scalars(
            select(Usuario).where(Usuario.id.in_({m.usuario_id for m in movimientos}))
        )
    }
    pendientes = db.scalar(
        select(func.count())
        .select_from(ComentarioLinea)
        .where(
            ComentarioLinea.hotel_id == contexto.hotel_id,
            ComentarioLinea.periodo == periodo,
            ComentarioLinea.padre_id.is_(None),
            ComentarioLinea.estatus == "pendiente",
        )
    )
    return CierreSalida(
        periodo=periodo,
        estado=estado,
        transiciones_posibles=pasos,
        historial=[
            TransicionSalida(
                desde=m.desde,
                hacia=m.hacia,
                usuario=nombres.get(m.usuario_id, "—"),
                nota=m.nota,
                creado_en=m.creado_en,
            )
            for m in movimientos
        ],
        version_mapeo_id=cierre.version_mapeo_id if cierre else None,
        version_plan_id=cierre.version_plan_id if cierre else None,
        version_estructura_id=cierre.version_estructura_id if cierre else None,
        huella_cifras=cierre.huella_cifras if cierre else None,
        congelado=cierre.congelado if cierre else None,
        comentarios_pendientes=pendientes or 0,
    )


@router.get("/hoteles/{hotel_id}/cierres", response_model=list[ResumenCierre])
def listar(contexto: Lectura, db: Session = Depends(get_db)) -> list[ResumenCierre]:
    filas = db.scalars(
        select(CierrePeriodo)
        .where(CierrePeriodo.hotel_id == contexto.hotel_id)
        .order_by(CierrePeriodo.periodo)
    )
    return [ResumenCierre(periodo=c.periodo, estado=c.estado) for c in filas]


@router.get("/hoteles/{hotel_id}/cierres/{periodo}", response_model=CierreSalida)
def detalle(contexto: Lectura, periodo: PeriodoRuta, db: Session = Depends(get_db)) -> CierreSalida:
    return _salida(db, contexto, periodo)


@router.post(
    "/hoteles/{hotel_id}/cierres/{periodo}/transiciones",
    response_model=CierreSalida,
    responses={
        409: {"description": "La transición no existe desde el estado actual, o falta el mapeo"},
        422: {"description": "Falta la nota que ese cambio exige"},
    },
)
def cambiar_estado(
    entrada: CambioEstado,
    contexto: Lectura,
    periodo: PeriodoRuta,
    db: Session = Depends(get_db),
) -> CierreSalida:
    permisos = {p: contexto.principal.puede(contexto.hotel_id, p) for p in Permiso}
    try:
        transicionar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            puede=permisos,
            periodo=periodo,
            hacia=entrada.hacia,
            nota=entrada.nota,
        )
    except CierreInvalido as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _salida(db, contexto, periodo)
