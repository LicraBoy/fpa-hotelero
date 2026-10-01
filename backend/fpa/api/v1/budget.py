"""Budget como versión inmutable del plan (Fase 3.1).

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Una versión no se
edita: reimportar crea otra y deja la anterior como `reemplazada`.
"""

import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import FechaHoraUtc, IdRuta
from fpa.calculo.ano_fiscal import etiqueta_ano_fiscal
from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.ingesta.variance_valores import leer_variance_valores
from fpa.modelos.plan import VersionPlan
from fpa.repositorios.plan import RepositorioPlan
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
from fpa.servicios.budget import importar_budget
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo

router = APIRouter(tags=["budget"], responses=RESPUESTAS_HOTEL)
log = logging.getLogger(__name__)
_RE_PERIODO = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
_HTTP = {
    Resolucion.CREADA: 201,
    Resolucion.REEMPLAZADA: 201,
    Resolucion.DUPLICADA: 200,
    Resolucion.REQUIERE_CONFIRMACION: 409,
    Resolucion.RECHAZADA: 422,
}

Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.BUDGET_LEER))]
Importacion = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.BUDGET_IMPORTAR))]


class VersionPlanSalida(BaseModel):
    id: int
    tipo: str
    numero: int
    ano_fiscal: str
    periodo_corte: str
    estado: str
    nombre_archivo: str
    sha256: str
    n_lineas: int
    version_estructura_id: int
    creada_en: FechaHoraUtc
    usuario_id: int | None
    reemplazada_en: FechaHoraUtc | None


class LineaPlanSalida(BaseModel):
    linea_id: int
    mes: Decimal | None
    ytd: Decimal | None
    anual: Decimal | None


class VersionPlanDetalle(VersionPlanSalida):
    lineas: list[LineaPlanSalida]


def _version(v: VersionPlan) -> VersionPlanSalida:
    return VersionPlanSalida(
        id=v.id,
        tipo=v.tipo,
        numero=v.numero,
        ano_fiscal=v.ano_fiscal,
        periodo_corte=v.periodo_corte,
        estado=v.estado,
        nombre_archivo=v.nombre_archivo,
        sha256=v.sha256,
        n_lineas=v.n_lineas,
        version_estructura_id=v.version_estructura_id,
        creada_en=v.creada_en,
        usuario_id=v.usuario_id,
        reemplazada_en=v.reemplazada_en,
    )


@router.get("/hoteles/{hotel_id}/budget/versiones", response_model=list[VersionPlanSalida])
def listar_versiones(contexto: Lectura, db: Session = Depends(get_db)) -> list[VersionPlanSalida]:
    return [_version(v) for v in RepositorioPlan(db, contexto.hotel_id).versiones()]


@router.get("/hoteles/{hotel_id}/budget/versiones/{version_id}", response_model=VersionPlanDetalle)
def detalle_version(
    version_id: IdRuta, contexto: Lectura, db: Session = Depends(get_db)
) -> VersionPlanDetalle:
    repo = RepositorioPlan(db, contexto.hotel_id)
    version = repo.obtener(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Versión de Budget no encontrada")
    return VersionPlanDetalle(
        **_version(version).model_dump(),
        lineas=[
            LineaPlanSalida(linea_id=x.linea_id, mes=x.mes, ytd=x.ytd, anual=x.anual)
            for x in repo.lineas(version.id)
        ],
    )


@router.post("/hoteles/{hotel_id}/budget/importar")
def importar(
    request: Request,
    contexto: Importacion,
    archivo: Annotated[UploadFile, File(description="Excel del Variance (.xlsx), hoja `Ago`")],
    periodo_corte: Annotated[
        str,
        Form(
            pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", description="AAAA-MM del archivo, p. ej. 2026-08"
        ),
    ],
    ano_fiscal: Annotated[str | None, Form(description="Por omisión se deduce del corte")] = None,
    confirmar_reemplazo: Annotated[bool, Form()] = False,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Carga el Budget (mes, YTD y anual) pegado en el Excel como una versión nueva e inmutable."""
    if not _RE_PERIODO.match(periodo_corte):
        raise HTTPException(status_code=422, detail="El periodo debe ser AAAA-MM")
    anio = ano_fiscal.strip() if ano_fiscal and ano_fiscal.strip() else None
    anio = anio or etiqueta_ano_fiscal(periodo_corte)
    limites = LimitesArchivo.desde_settings()
    nombre = nombre_seguro(archivo.filename)

    def rechazar(motivo: str, estado: int) -> None:
        auditar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            accion="budget.archivo_rechazado",
            entidad="version_plan",
            detalle={"archivo": nombre, "motivo": motivo, "http": estado},
        )
        db.commit()

    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > limites.max_bytes + 64 * 1024:
        rechazar("Archivo demasiado grande", 413)
        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo")

    estructura = RepositorioReporte(db, contexto.hotel_id).vigente()
    if estructura is None:
        raise HTTPException(
            status_code=409, detail="Primero importa la estructura del reporte (reporte/importar)"
        )

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
            valores = leer_variance_valores(temporal)
        except ValueError as e:
            rechazar(str(e), 422)
            raise HTTPException(status_code=422, detail=str(e)) from None
        except Exception:
            log.exception("No se pudo leer el libro del Variance")
            rechazar("No se pudo leer el libro", 422)
            raise HTTPException(status_code=422, detail="No se pudo leer el libro") from None

        resultado = importar_budget(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            version_estructura=estructura,
            valores=valores,
            archivo=DatosArchivo(nombre=nombre, sha256=sha256, tamano_bytes=tamano),
            periodo_corte=periodo_corte,
            ano_fiscal=anio,
            confirmar_reemplazo=confirmar_reemplazo,
        )
        db.commit()
        cuerpo: dict[str, object] = {
            "resolucion": resultado.resolucion.value,
            "motivos": resultado.motivos,
            "avisos": resultado.avisos,
            "version": _version(resultado.version).model_dump(mode="json")
            if resultado.version
            else None,
        }
        return JSONResponse(status_code=_HTTP[resultado.resolucion], content=cuerpo)
    finally:
        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                log.warning("No se pudo borrar el temporal %s; se limpiará después", temporal.name)
