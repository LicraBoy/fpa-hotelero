import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.ingesta.novohit_con020 import leer_con020
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.seguridad.archivos import (
    ArchivoRechazado,
    LimitesArchivo,
    guardar_en_temporal,
    inspeccionar_xls,
    limpiar_temporales,
    nombre_seguro,
    verificar_nombre_xls,
)
from fpa.servicios.auditoria import auditar
from fpa.servicios.catalogo import NodoCatalogo, construir_arbol
from fpa.servicios.catalogo_oficial import importar_catalogo

router = APIRouter(tags=["catalogo"])
log = logging.getLogger(__name__)


class NodoSalida(BaseModel):
    codigo: str
    descripcion: str | None
    clase: str
    nivel: int | None
    con_movimientos: bool
    es_titulo: bool
    sin_jerarquia: bool
    tipo: str | None
    grupo_ef: str | None
    depto_ef: str | None
    cuenta_sat: str | None
    activa: bool
    en_catalogo_oficial: bool
    hijos: list["NodoSalida"]


def _a_salida(nodo: NodoCatalogo) -> NodoSalida:
    return NodoSalida(
        codigo=nodo.codigo,
        descripcion=nodo.descripcion,
        clase=nodo.clase,
        nivel=nodo.nivel,
        con_movimientos=nodo.con_movimientos,
        es_titulo=nodo.es_titulo,
        sin_jerarquia=nodo.sin_jerarquia,
        tipo=nodo.tipo,
        grupo_ef=nodo.grupo_ef,
        depto_ef=nodo.depto_ef,
        cuenta_sat=nodo.cuenta_sat,
        activa=nodo.activa,
        en_catalogo_oficial=nodo.en_catalogo_oficial,
        hijos=[_a_salida(h) for h in nodo.hijos],
    )


@router.get("/hoteles/{hotel_id}/catalogo/arbol", response_model=list[NodoSalida])
def arbol_del_catalogo(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CATALOGO_LEER))],
    db: Session = Depends(get_db),
) -> list[NodoSalida]:
    """Árbol de cuentas locales del hotel (títulos de la jerarquía y cuentas)."""
    cuentas = RepositorioCatalogo(db, contexto.hotel_id).todas()
    return [_a_salida(n) for n in construir_arbol(cuentas)]


class RespuestaImportacion(BaseModel):
    resolucion: str  # importado | sin_cambio | rechazado
    total_cuentas: int
    total_titulos: int
    creadas: int
    actualizadas: int
    sin_cambio: int
    titulos_con_nombre_nuevo: int
    fuera_del_catalogo: list[str]
    inactivas_con_movimientos: list[str]
    ya_no_vienen: list[str]
    avisos: list[str]
    motivos: list[str]


def _vacia(motivos: list[str]) -> RespuestaImportacion:
    return RespuestaImportacion(
        resolucion="rechazado",
        total_cuentas=0,
        total_titulos=0,
        creadas=0,
        actualizadas=0,
        sin_cambio=0,
        titulos_con_nombre_nuevo=0,
        fuera_del_catalogo=[],
        inactivas_con_movimientos=[],
        ya_no_vienen=[],
        avisos=[],
        motivos=motivos,
    )


@router.post("/hoteles/{hotel_id}/catalogo/importar")
def importar_catalogo_oficial(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CATALOGO_IMPORTAR))],
    archivo: Annotated[UploadFile, File(description="Catálogo contable (CON020) en formato .xls")],
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Importa el catálogo contable oficial de Novohit (reporte CON020, .xls)."""
    limites = LimitesArchivo.desde_settings()
    nombre = nombre_seguro(archivo.filename)
    carpeta_temporal = Path(settings.storage_dir) / "tmp"
    limpiar_temporales(carpeta_temporal)
    temporal: Path | None = None

    def rechazar(motivo: str, estado: int, accion: str = "catalogo.archivo_rechazado") -> None:
        auditar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            accion=accion,
            entidad="catalogo",
            detalle={"archivo": nombre, "motivo": motivo, "http": estado},
        )
        db.commit()

    try:
        try:
            verificar_nombre_xls(nombre)
            temporal, sha256, tamano = guardar_en_temporal(
                archivo.file, carpeta_temporal, limites, sufijo=".xls"
            )
            inspeccionar_xls(temporal)
        except ArchivoRechazado as e:
            rechazar(e.detalle, e.status_code)
            raise HTTPException(status_code=e.status_code, detail=e.detalle) from None

        try:
            catalogo = leer_con020(temporal)
        except ValueError as e:
            rechazar(str(e), 422)
            raise HTTPException(status_code=422, detail=str(e)) from None
        except Exception:
            log.exception("No se pudo leer el catálogo subido")
            rechazar("No se pudo leer el libro", 422)
            raise HTTPException(status_code=422, detail="No se pudo leer el libro") from None

        if not catalogo.es_valido:
            motivos = catalogo.errores[:10]
            rechazar("; ".join(motivos), 422, accion="catalogo.rechazado")
            return JSONResponse(status_code=422, content=_vacia(motivos).model_dump(mode="json"))

        with db.begin_nested():
            resumen = importar_catalogo(db, hotel_id=contexto.hotel_id, catalogo=catalogo)
            auditar(
                db,
                organizacion_id=contexto.organizacion_id,
                hotel_id=contexto.hotel_id,
                usuario_id=contexto.principal.usuario_id,
                accion="catalogo.importado" if resumen.hubo_cambios else "catalogo.sin_cambio",
                entidad="catalogo",
                detalle={
                    "archivo": nombre,
                    "sha256": sha256,
                    "tamano_bytes": tamano,
                    "empresa": catalogo.empresa,
                    "fecha_emision": catalogo.fecha_emision,
                    "total_cuentas": resumen.total_cuentas,
                    "total_titulos": resumen.total_titulos,
                    "creadas": resumen.creadas,
                    "actualizadas": resumen.actualizadas,
                    "fuera_del_catalogo": len(resumen.fuera_del_catalogo),
                    "ya_no_vienen": len(resumen.ya_no_vienen),
                },
            )
        db.commit()

        if resumen.hubo_cambios:
            final = (
                Path(settings.storage_dir) / "catalogos" / str(contexto.hotel_id) / f"{sha256}.xls"
            )
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                temporal.unlink(missing_ok=True)
            else:
                temporal.replace(final)
            temporal = None

        respuesta = RespuestaImportacion(
            resolucion="importado" if resumen.hubo_cambios else "sin_cambio",
            total_cuentas=resumen.total_cuentas,
            total_titulos=resumen.total_titulos,
            creadas=resumen.creadas,
            actualizadas=resumen.actualizadas,
            sin_cambio=resumen.sin_cambio,
            titulos_con_nombre_nuevo=resumen.titulos_con_nombre_nuevo,
            fuera_del_catalogo=resumen.fuera_del_catalogo[:200],
            inactivas_con_movimientos=resumen.inactivas_con_movimientos[:200],
            ya_no_vienen=resumen.ya_no_vienen[:200],
            avisos=catalogo.avisos[:20],
            motivos=[],
        )
        return JSONResponse(
            status_code=201 if resumen.hubo_cambios else 200,
            content=respuesta.model_dump(mode="json"),
        )
    finally:
        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                log.warning("No se pudo borrar el temporal %s; se limpiará después", temporal.name)
