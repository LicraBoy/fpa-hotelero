"""Carga de archivos y consulta de cargas y auditoría (Fase 1.8)."""

import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import FechaHoraUtc, IdRuta
from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.modelos.cargas import CargaArchivo
from fpa.repositorios.auditoria import RepositorioAuditoria
from fpa.repositorios.cargas import RepositorioCargas
from fpa.seguridad.archivos import (
    ArchivoRechazado,
    LimitesArchivo,
    guardar_en_temporal,
    inspeccionar_xlsx,
    limpiar_temporales,
    nombre_seguro,
    verificar_nombre,
)
from fpa.servicios.auditoria import auditar
from fpa.servicios.cargar_archivo import Resolucion, ResultadoCarga, cargar_archivo
from fpa.servicios.cargas import DatosArchivo

router = APIRouter(tags=["cargas"], responses=RESPUESTAS_HOTEL)
log = logging.getLogger(__name__)
_RE_PERIODO = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")

_HTTP_POR_RESOLUCION = {
    Resolucion.CREADA: 201,
    Resolucion.REEMPLAZADA: 201,
    Resolucion.DUPLICADA: 200,
    Resolucion.REQUIERE_CONFIRMACION: 409,
    Resolucion.RECHAZADA: 422,
}


class CargaSalida(BaseModel):
    id: int
    periodo: str
    fuente: str
    estado: str
    nombre_archivo: str
    sha256: str
    n_movimientos: int
    total_debito: Decimal
    total_credito: Decimal
    fecha_min: date
    fecha_max: date
    creado_en: FechaHoraUtc
    usuario_id: int | None
    reemplazada_por_id: int | None


class CargaDetalle(CargaSalida):
    controles: dict[str, Any] | None


class ConflictoSalida(BaseModel):
    periodo: str
    carga_vigente_id: int
    archivo_vigente: str
    n_vigente: int
    debito_vigente: Decimal
    credito_vigente: Decimal
    n_nuevo: int
    debito_nuevo: Decimal
    credito_nuevo: Decimal


class RespuestaCarga(BaseModel):
    resolucion: str
    cargas: list[CargaSalida]
    reemplazadas: list[CargaSalida]
    conflictos: list[ConflictoSalida]
    sin_cambio: list[str]
    motivos: list[str]
    reporte: dict[str, Any] | None


class EventoSalida(BaseModel):
    id: int
    accion: str
    entidad: str
    entidad_id: int | None
    usuario_id: int | None
    detalle: dict[str, Any] | None
    creado_en: FechaHoraUtc


def _carga_salida(c: CargaArchivo) -> CargaSalida:
    return CargaSalida(
        id=c.id,
        periodo=c.periodo,
        fuente=c.fuente,
        estado=c.estado,
        nombre_archivo=c.nombre_archivo,
        sha256=c.sha256,
        n_movimientos=c.n_movimientos,
        total_debito=c.total_debito,
        total_credito=c.total_credito,
        fecha_min=c.fecha_min,
        fecha_max=c.fecha_max,
        creado_en=c.creado_en,
        usuario_id=c.usuario_id,
        reemplazada_por_id=c.reemplazada_por_id,
    )


def _respuesta(r: ResultadoCarga) -> RespuestaCarga:
    return RespuestaCarga(
        resolucion=r.resolucion.value,
        cargas=[_carga_salida(c) for c in r.cargas],
        reemplazadas=[_carga_salida(c) for c in r.reemplazadas],
        conflictos=[ConflictoSalida(**vars(c)) for c in r.conflictos],
        sin_cambio=r.sin_cambio,
        motivos=r.motivos,
        reporte=r.reporte.a_dict() if r.reporte else None,
    )


def _periodos_declarados(texto: str | None) -> list[str] | None:
    if not texto or not texto.strip():
        return None
    periodos = [p.strip() for p in texto.split(",") if p.strip()]
    if not periodos or not all(_RE_PERIODO.match(p) for p in periodos):
        raise HTTPException(
            status_code=422, detail="Los periodos deben ser AAAA-MM separados por coma"
        )
    return periodos


def _leer(fuente: Fuente, ruta: Path) -> ResultadoLectura:
    if fuente == Fuente.CON130:
        return leer_con130(ruta)
    return leer_variance_base_datos(ruta)


def _ruta_final(hotel_id: int, sha256: str) -> Path:
    # La ruta se arma solo con un entero y un hash hexadecimal: no hay forma de salirse de storage/
    return Path(settings.storage_dir) / "cargas" / str(hotel_id) / f"{sha256}.xlsx"


@router.post("/hoteles/{hotel_id}/cargas")
def subir_carga(
    request: Request,
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CARGA_CREAR))],
    archivo: Annotated[
        UploadFile, File(description="Libro .xlsx exportado de Novohit o el Variance")
    ],
    fuente: Annotated[Fuente, Form(description="con130 o variance_base_datos")],
    confirmar_reemplazo: Annotated[bool, Form()] = False,
    periodos: Annotated[
        str | None, Form(description="Opcional: AAAA-MM,AAAA-MM que declara el archivo")
    ] = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    limites = LimitesArchivo.desde_settings()
    nombre = nombre_seguro(archivo.filename)
    declarados = _periodos_declarados(periodos)

    def auditar_rechazo(motivo: str, estado: int) -> None:
        auditar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            accion="carga.archivo_rechazado",
            entidad="carga_archivo",
            detalle={"archivo": nombre, "motivo": motivo, "http": estado},
        )
        db.commit()

    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > limites.max_bytes + 64 * 1024:
        # Rechazo temprano por la cabecera; el conteo real por bloques es el que manda.
        auditar_rechazo("Archivo demasiado grande", 413)
        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo")

    carpeta_temporal = Path(settings.storage_dir) / "tmp"
    limpiar_temporales(carpeta_temporal)
    temporal: Path | None = None
    try:
        try:
            verificar_nombre(nombre)
            temporal, sha256, tamano = guardar_en_temporal(archivo.file, carpeta_temporal, limites)
            inspeccionar_xlsx(temporal, limites)
        except ArchivoRechazado as e:
            auditar_rechazo(e.detalle, e.status_code)
            raise HTTPException(status_code=e.status_code, detail=e.detalle) from None

        try:
            lectura = _leer(fuente, temporal)
        except ValueError as e:
            auditar_rechazo(str(e), 422)
            raise HTTPException(status_code=422, detail=str(e)) from None
        except Exception:
            log.exception("No se pudo leer el archivo subido")
            auditar_rechazo("No se pudo leer el libro", 422)
            raise HTTPException(status_code=422, detail="No se pudo leer el libro") from None

        resultado = cargar_archivo(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            resultado=lectura,
            archivo=DatosArchivo(nombre=nombre, sha256=sha256, tamano_bytes=tamano),
            confirmar_reemplazo=confirmar_reemplazo,
            periodos_esperados=declarados,
        )
        db.commit()

        if resultado.resolucion in (Resolucion.CREADA, Resolucion.REEMPLAZADA):
            final = _ruta_final(contexto.hotel_id, sha256)
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                temporal.unlink(missing_ok=True)
            else:
                temporal.replace(final)
            temporal = None
        return JSONResponse(
            status_code=_HTTP_POR_RESOLUCION[resultado.resolucion],
            content=_respuesta(resultado).model_dump(mode="json"),
        )
    finally:
        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                log.warning("No se pudo borrar el temporal %s; se limpiará después", temporal.name)


@router.get("/hoteles/{hotel_id}/cargas", response_model=list[CargaSalida])
def listar_cargas(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CARGA_LEER))],
    db: Session = Depends(get_db),
) -> list[CargaSalida]:
    return [_carga_salida(c) for c in RepositorioCargas(db, contexto.hotel_id).listar()]


@router.get("/hoteles/{hotel_id}/cargas/{carga_id}", response_model=CargaDetalle)
def detalle_carga(
    carga_id: IdRuta,
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CARGA_LEER))],
    db: Session = Depends(get_db),
) -> CargaDetalle:
    carga = RepositorioCargas(db, contexto.hotel_id).obtener(carga_id)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    return CargaDetalle(**_carga_salida(carga).model_dump(), controles=carga.controles)


@router.get("/hoteles/{hotel_id}/auditoria", response_model=list[EventoSalida])
def listar_auditoria(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.AUDITORIA_LEER))],
    db: Session = Depends(get_db),
) -> list[EventoSalida]:
    return [
        EventoSalida(
            id=e.id,
            accion=e.accion,
            entidad=e.entidad,
            entidad_id=e.entidad_id,
            usuario_id=e.usuario_id,
            detalle=e.detalle,
            creado_en=e.creado_en,
        )
        for e in RepositorioAuditoria(db, contexto.hotel_id).listar()
    ]
