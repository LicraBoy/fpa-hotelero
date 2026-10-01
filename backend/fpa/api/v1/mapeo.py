"""Estructura del reporte Variance y mapeo de cuentas a líneas (Fase 2.6).

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Cada cambio queda
en la bitácora. Solo se edita un borrador; una versión aprobada es inmutable (409).
"""

import logging
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import ID_MAX, FechaHoraUtc, IdConsulta, IdRuta
from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.ingesta.variance_estructura import leer_filas_hoja, leer_variance_estructura_filas
from fpa.ingesta.variance_mapeo import leer_variance_mapeo_filas
from fpa.ingesta.variance_reglas import leer_variance_reglas_filas
from fpa.modelos.mapeo import VersionMapeo
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
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
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.reglas_suma import importar_reglas_suma
from fpa.servicios.validacion_mapeo import validar_mapeo
from fpa.servicios.versionado_mapeo import (
    AprobacionBloqueada,
    MapeoInvalido,
    VersionInmutable,
    agregar_vinculo,
    aprobar,
    crear_borrador_desde,
    descartar_borrador,
    excluir_cuenta,
    quitar_exclusion,
    quitar_vinculo,
)

router = APIRouter(tags=["mapeo"], responses=RESPUESTAS_HOTEL)
log = logging.getLogger(__name__)
_RE_PERIODO = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")

Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.MAPEO_LEER))]
LecturaReporte = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.REPORTE_LEER))]
Edicion = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.MAPEO_EDITAR))]
Aprobacion = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.MAPEO_APROBAR))]


# --- Esquemas ---------------------------------------------------------------------------------


class LineaSalida(BaseModel):
    id: int
    orden: int
    tipo: str
    nivel: int
    seccion_id: int | None
    codigo_corporativo: str | None
    descripcion: str
    clave: str
    fila_origen: int


class EstructuraSalida(BaseModel):
    version_id: int
    nombre_archivo: str
    periodo_referencia: str | None
    creado_en: FechaHoraUtc
    n_lineas: int
    n_detalle: int
    lineas: list[LineaSalida]


class VersionSalida(BaseModel):
    id: int
    numero: int
    estado: str
    origen: str
    version_estructura_id: int
    notas: str | None
    creada_en: FechaHoraUtc
    creada_por_id: int | None
    aprobada_en: FechaHoraUtc | None
    aprobada_por_id: int | None


class VinculoSalida(BaseModel):
    linea_id: int
    cuenta_codigo: str
    signo: int
    origen: str


class ExclusionSalida(BaseModel):
    cuenta_codigo: str
    motivo: str
    usuario_id: int | None
    creada_en: FechaHoraUtc


class VersionDetalle(VersionSalida):
    vinculos: list[VinculoSalida]
    excluidas: list[ExclusionSalida]


class VinculoEntrada(BaseModel):
    linea_id: Annotated[int, Field(ge=1, le=ID_MAX)]
    cuenta_codigo: str = Field(min_length=1, max_length=40)
    signo: int


class ExclusionEntrada(BaseModel):
    cuenta_codigo: str = Field(min_length=1, max_length=40)
    motivo: str = Field(min_length=1, max_length=500)


class CopiaEntrada(BaseModel):
    version_origen_id: Annotated[int | None, Field(ge=1, le=ID_MAX)] = None


class AprobacionEntrada(BaseModel):
    periodos: list[str] | None = None
    notas: str | None = Field(default=None, max_length=2000)


def _version(v: VersionMapeo) -> VersionSalida:
    return VersionSalida(
        id=v.id,
        numero=v.numero,
        estado=v.estado,
        origen=v.origen,
        version_estructura_id=v.version_estructura_id,
        notas=v.notas,
        creada_en=v.creada_en,
        creada_por_id=v.creada_por_id,
        aprobada_en=v.aprobada_en,
        aprobada_por_id=v.aprobada_por_id,
    )


def _error(e: Exception) -> HTTPException:
    """Traduce las excepciones de negocio a respuestas HTTP."""
    if isinstance(e, LookupError):
        return HTTPException(status_code=404, detail=str(e.args[0]) if e.args else "No encontrado")
    if isinstance(e, VersionInmutable):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, AprobacionBloqueada):
        return HTTPException(status_code=409, detail={"motivos": e.motivos})
    return HTTPException(status_code=422, detail=str(e))


# --- Lectura ----------------------------------------------------------------------------------


@router.get("/hoteles/{hotel_id}/reporte/estructura", response_model=EstructuraSalida)
def estructura_vigente(contexto: LecturaReporte, db: Session = Depends(get_db)) -> EstructuraSalida:
    repo = RepositorioReporte(db, contexto.hotel_id)
    version = repo.vigente()
    if version is None:
        raise HTTPException(status_code=404, detail="Aún no se importa la estructura del reporte")
    return EstructuraSalida(
        version_id=version.id,
        nombre_archivo=version.nombre_archivo,
        periodo_referencia=version.periodo_referencia,
        creado_en=version.creado_en,
        n_lineas=version.n_lineas,
        n_detalle=version.n_detalle,
        lineas=[
            LineaSalida(
                id=x.id,
                orden=x.orden,
                tipo=x.tipo,
                nivel=x.nivel,
                seccion_id=x.seccion_id,
                codigo_corporativo=x.codigo_corporativo,
                descripcion=x.descripcion,
                clave=x.clave,
                fila_origen=x.fila_origen,
            )
            for x in repo.lineas(version.id)
        ],
    )


@router.get("/hoteles/{hotel_id}/mapeo/versiones", response_model=list[VersionSalida])
def listar_versiones(contexto: Lectura, db: Session = Depends(get_db)) -> list[VersionSalida]:
    return [_version(v) for v in RepositorioMapeo(db, contexto.hotel_id).versiones()]


@router.get("/hoteles/{hotel_id}/mapeo/versiones/{version_id}", response_model=VersionDetalle)
def detalle_version(
    version_id: IdRuta, contexto: Lectura, db: Session = Depends(get_db)
) -> VersionDetalle:
    repo = RepositorioMapeo(db, contexto.hotel_id)
    version = repo.obtener(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Versión de mapeo no encontrada")
    return VersionDetalle(
        **_version(version).model_dump(),
        vinculos=[
            VinculoSalida(
                linea_id=v.linea_id, cuenta_codigo=v.cuenta_codigo, signo=v.signo, origen=v.origen
            )
            for v in repo.vinculos(version.id)
        ],
        excluidas=[
            ExclusionSalida(
                cuenta_codigo=e.cuenta_codigo,
                motivo=e.motivo,
                usuario_id=e.usuario_id,
                creada_en=e.creada_en,
            )
            for e in repo.excluidas(version.id)
        ],
    )


@router.get("/hoteles/{hotel_id}/mapeo/versiones/{version_id}/validacion")
def validacion(
    version_id: IdRuta,
    contexto: Lectura,
    periodo: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", description="AAAA-MM")],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not _RE_PERIODO.match(periodo):
        raise HTTPException(status_code=422, detail="El periodo debe ser AAAA-MM")
    try:
        return validar_mapeo(
            db, hotel_id=contexto.hotel_id, version_mapeo_id=version_id, periodo=periodo
        ).a_dict()
    except LookupError as e:
        raise _error(e) from None


# --- Edición (solo borradores) ------------------------------------------------------------------


def _kw(contexto: ContextoHotel) -> dict[str, Any]:
    return {
        "organizacion_id": contexto.organizacion_id,
        "hotel_id": contexto.hotel_id,
        "usuario_id": contexto.principal.usuario_id,
    }


@router.post("/hoteles/{hotel_id}/mapeo/versiones", response_model=VersionSalida, status_code=201)
def crear_borrador(
    contexto: Edicion, entrada: CopiaEntrada | None = None, db: Session = Depends(get_db)
) -> VersionSalida:
    """Crea un borrador copiando la versión aprobada (o la indicada)."""
    try:
        nueva = crear_borrador_desde(
            db,
            version_origen_id=entrada.version_origen_id if entrada else None,
            **_kw(contexto),
        )
        db.commit()
    except (LookupError, MapeoInvalido) as e:
        db.rollback()
        raise _error(e) from None
    return _version(nueva)


@router.put(
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/vinculos", response_model=VinculoSalida
)
def poner_vinculo(
    version_id: IdRuta, entrada: VinculoEntrada, contexto: Edicion, db: Session = Depends(get_db)
) -> VinculoSalida:
    try:
        v = agregar_vinculo(
            db,
            version_id=version_id,
            linea_id=entrada.linea_id,
            cuenta_codigo=entrada.cuenta_codigo,
            signo=entrada.signo,
            **_kw(contexto),
        )
        db.commit()
    except (LookupError, VersionInmutable, MapeoInvalido) as e:
        db.rollback()
        raise _error(e) from None
    return VinculoSalida(
        linea_id=v.linea_id, cuenta_codigo=v.cuenta_codigo, signo=v.signo, origen=v.origen
    )


@router.delete("/hoteles/{hotel_id}/mapeo/versiones/{version_id}/vinculos", status_code=204)
def borrar_vinculo(
    version_id: IdRuta,
    contexto: Edicion,
    linea_id: IdConsulta,
    cuenta_codigo: Annotated[str, Query(min_length=1, max_length=40)],
    db: Session = Depends(get_db),
) -> None:
    try:
        quitar_vinculo(
            db,
            version_id=version_id,
            linea_id=linea_id,
            cuenta_codigo=cuenta_codigo,
            **_kw(contexto),
        )
        db.commit()
    except (LookupError, VersionInmutable) as e:
        db.rollback()
        raise _error(e) from None


@router.put(
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/exclusiones", response_model=ExclusionSalida
)
def poner_exclusion(
    version_id: IdRuta, entrada: ExclusionEntrada, contexto: Edicion, db: Session = Depends(get_db)
) -> ExclusionSalida:
    try:
        e = excluir_cuenta(
            db,
            version_id=version_id,
            cuenta_codigo=entrada.cuenta_codigo,
            motivo=entrada.motivo,
            **_kw(contexto),
        )
        db.commit()
    except (LookupError, VersionInmutable, MapeoInvalido) as err:
        db.rollback()
        raise _error(err) from None
    return ExclusionSalida(
        cuenta_codigo=e.cuenta_codigo,
        motivo=e.motivo,
        usuario_id=e.usuario_id,
        creada_en=e.creada_en,
    )


@router.delete("/hoteles/{hotel_id}/mapeo/versiones/{version_id}/exclusiones", status_code=204)
def borrar_exclusion(
    version_id: IdRuta,
    contexto: Edicion,
    cuenta_codigo: Annotated[str, Query(min_length=1, max_length=40)],
    db: Session = Depends(get_db),
) -> None:
    try:
        quitar_exclusion(db, version_id=version_id, cuenta_codigo=cuenta_codigo, **_kw(contexto))
        db.commit()
    except (LookupError, VersionInmutable) as e:
        db.rollback()
        raise _error(e) from None


@router.post("/hoteles/{hotel_id}/mapeo/versiones/{version_id}/descartar", status_code=204)
def descartar(version_id: IdRuta, contexto: Edicion, db: Session = Depends(get_db)) -> None:
    try:
        descartar_borrador(db, version_id=version_id, **_kw(contexto))
        db.commit()
    except (LookupError, VersionInmutable) as e:
        db.rollback()
        raise _error(e) from None


@router.post(
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/aprobar", response_model=VersionSalida
)
def aprobar_version(
    version_id: IdRuta,
    contexto: Aprobacion,
    entrada: AprobacionEntrada | None = None,
    db: Session = Depends(get_db),
) -> VersionSalida:
    """Aprueba un borrador (solo Contraloría). 409 si deja cuentas con movimiento sin mapear."""
    periodos = entrada.periodos if entrada else None
    if periodos and not all(_RE_PERIODO.match(p) for p in periodos):
        raise HTTPException(status_code=422, detail="Los periodos deben ser AAAA-MM")
    try:
        version = aprobar(
            db,
            version_id=version_id,
            periodos=periodos,
            notas=entrada.notas if entrada else None,
            **_kw(contexto),
        )
        db.commit()
    except (LookupError, VersionInmutable, AprobacionBloqueada) as e:
        db.rollback()
        raise _error(e) from None
    return _version(version)


# --- Importación del Excel del Variance --------------------------------------------------------


@router.post("/hoteles/{hotel_id}/reporte/importar")
def importar_reporte(
    request: Request,
    contexto: Edicion,
    archivo: Annotated[UploadFile, File(description="Excel del Variance (.xlsx), hoja `Ago`")],
    periodo_referencia: Annotated[str | None, Form(description="AAAA-MM del archivo")] = None,
    confirmar_reemplazo: Annotated[bool, Form()] = False,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Importa estructura, reglas de suma y un **borrador** de mapeo desde el Excel del Variance."""
    limites = LimitesArchivo.desde_settings()
    nombre = nombre_seguro(archivo.filename)
    if periodo_referencia is not None and not _RE_PERIODO.match(periodo_referencia):
        raise HTTPException(status_code=422, detail="El periodo debe ser AAAA-MM")

    def rechazar(motivo: str, estado: int) -> None:
        auditar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            accion="estructura.archivo_rechazado",
            entidad="estructura_reporte",
            detalle={"archivo": nombre, "motivo": motivo, "http": estado},
        )
        db.commit()

    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > limites.max_bytes + 64 * 1024:
        rechazar("Archivo demasiado grande", 413)
        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo")

    carpeta = Path(settings.storage_dir) / "tmp"
    limpiar_temporales(carpeta)
    temporal: Path | None = None
    try:
        try:
            verificar_nombre(nombre)
            temporal, sha256, tamano = guardar_en_temporal(archivo.file, carpeta, limites)
            inspeccionar_xlsx(temporal, limites)
        except ArchivoRechazado as e:
            rechazar(e.detalle, e.status_code)
            raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
        try:
            filas = leer_filas_hoja(temporal)
        except ValueError as e:
            rechazar(str(e), 422)
            raise HTTPException(status_code=422, detail=str(e)) from None
        except Exception:
            log.exception("No se pudo leer el libro del Variance")
            rechazar("No se pudo leer el libro", 422)
            raise HTTPException(status_code=422, detail="No se pudo leer el libro") from None

        estructura = leer_variance_estructura_filas(filas)
        reglas = leer_variance_reglas_filas(filas, estructura)
        mapeo = leer_variance_mapeo_filas(filas, estructura)
        datos = DatosArchivo(nombre=nombre, sha256=sha256, tamano_bytes=tamano)
        kw = _kw(contexto)

        # Nada se escribe hasta tener la confirmación de todo lo que se va a reemplazar.
        if not estructura.es_valido or not mapeo.es_valido:
            motivos = [*estructura.errores, *mapeo.errores][:10]
            rechazar("; ".join(motivos), 422)
            return JSONResponse(
                status_code=422, content={"resolucion": "rechazada", "motivos": motivos}
            )
        vigente = RepositorioReporte(db, contexto.hotel_id).vigente()
        borrador = RepositorioMapeo(db, contexto.hotel_id).borrador()
        pendientes = []
        if vigente is not None and vigente.sha256 != sha256:
            pendientes.append(f"Reemplazar la estructura vigente ({vigente.nombre_archivo})")
        if borrador is not None:
            pendientes.append(f"Descartar el borrador de mapeo (versión {borrador.numero})")
        if pendientes and not confirmar_reemplazo:
            return JSONResponse(
                status_code=409,
                content={"resolucion": "requiere_confirmacion", "motivos": pendientes},
            )

        res_est = importar_estructura_reporte(
            db,
            resultado=estructura,
            archivo=datos,
            periodo_referencia=periodo_referencia,
            confirmar_reemplazo=confirmar_reemplazo,
            **kw,
        )
        version = res_est.version
        if res_est.resolucion is Resolucion.REQUIERE_CONFIRMACION or version is None:
            db.rollback()
            return JSONResponse(
                status_code=409,
                content={"resolucion": "requiere_confirmacion", "motivos": res_est.motivos},
            )
        n_reglas = importar_reglas_suma(db, version=version, leidas=reglas, **kw)
        res_map = importar_mapeo(
            db,
            version_estructura=version,
            leido=mapeo,
            archivo=datos,
            confirmar_reemplazo=confirmar_reemplazo,
            **kw,
        )
        db.commit()

        if res_est.resolucion in (Resolucion.CREADA, Resolucion.REEMPLAZADA):
            final = (
                Path(settings.storage_dir) / "variance" / str(contexto.hotel_id) / f"{sha256}.xlsx"
            )
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                temporal.unlink(missing_ok=True)
            else:
                temporal.replace(final)
            temporal = None
        return JSONResponse(
            status_code=201,
            content={
                "resolucion": res_est.resolucion.value,
                "estructura_version_id": version.id,
                "n_lineas": version.n_lineas,
                "n_detalle": version.n_detalle,
                "n_reglas_suma": n_reglas,
                "mapeo_version_id": res_map.version.id if res_map.version else None,
                "mapeo_numero": res_map.version.numero if res_map.version else None,
                "n_vinculos": res_map.n_vinculos,
                "lineas_vinculadas": res_map.lineas_vinculadas,
                "cuentas_sin_catalogo": res_map.sin_catalogo[:200],
                "avisos": [*estructura.avisos, *reglas.avisos, *mapeo.avisos][:30],
            },
        )
    finally:
        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                log.warning("No se pudo borrar el temporal %s; se limpiará después", temporal.name)
