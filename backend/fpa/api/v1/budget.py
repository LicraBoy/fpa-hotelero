"""Budget como versión inmutable del plan (Fase 3.1).

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Una versión no se
edita: reimportar crea otra y deja la anterior como `reemplazada`.
"""

import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi import Path as RutaPath
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import ID_MAX, FechaHoraUtc, IdRuta
from fpa.calculo.ano_fiscal import etiqueta_ano_fiscal
from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado, principal_actual
from fpa.identidad.permisos import Permiso
from fpa.identidad.principal import Principal
from fpa.ingesta.budget_anual_mzt import (
    alinear_con_lineas,
    es_budget_anual_mzt,
    leer_budget_anual,
)
from fpa.ingesta.formato_variance import Formato, detectar_formato
from fpa.ingesta.variance_lectura import leer_variance
from fpa.ingesta.variance_mzt import leer_hojas_mzt, leer_valores_mensuales_mzt
from fpa.ingesta.variance_valores import ValoresFila, leer_variance_valores
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
from fpa.servicios.budget import importar_budget, importar_budget_mensual
from fpa.servicios.budget_edicion import (
    BaseDesactualizada,
    CambioBudget,
    EdicionInvalida,
    crear_version_desde_cambios,
    vista_edicion,
)
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.valores_capturados import CapturaInvalida, ValorEntrada, capturar_actuales

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


def _leer_o_capturar(
    hotel_id: Annotated[int, RutaPath(ge=1, le=2_147_483_647)],
    principal: Principal = Depends(principal_actual),
) -> ContextoHotel:
    """Ver la grilla de Budget (pantalla fusionada con el ciclo de Presupuesto): no exige
    `budget:importar` — basta con poder capturar, fijar el objetivo, revisarla o leerla."""
    if not principal.tiene_acceso_a(hotel_id):
        raise HTTPException(status_code=404, detail="Hotel no encontrado")
    if not (
        principal.puede(hotel_id, Permiso.BUDGET_LEER)
        or principal.puede(hotel_id, Permiso.BUDGET_IMPORTAR)
        or principal.puede(hotel_id, Permiso.BUDGET_CAPTURAR)
        or principal.puede(hotel_id, Permiso.BUDGET_OBJETIVO)
        or principal.puede(hotel_id, Permiso.BUDGET_REVISAR)
    ):
        raise HTTPException(status_code=403, detail="Sin permiso para esta acción")
    return ContextoHotel(principal=principal, hotel_id=hotel_id)


LecturaOCaptura = Annotated[ContextoHotel, Depends(_leer_o_capturar)]


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
def listar_versiones(
    contexto: LecturaOCaptura, db: Session = Depends(get_db)
) -> list[VersionPlanSalida]:
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
        str | None,
        Form(
            pattern=r"^20\d{2}-(0[1-9]|1[0-2])$",
            description="AAAA-MM del archivo, p. ej. 2026-08. Obligatorio en el formato de "
            "Vallarta; el de Mazatlán trae sus meses (julio y agosto) en el propio archivo",
        ),
    ] = None,
    ano_fiscal: Annotated[str | None, Form(description="Por omisión se deduce del corte")] = None,
    confirmar_reemplazo: Annotated[bool, Form()] = False,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Carga el Budget (mes, YTD y anual) pegado en el Excel como una versión nueva e inmutable."""
    if periodo_corte is not None and not _RE_PERIODO.match(periodo_corte):
        raise HTTPException(status_code=422, detail="El periodo debe ser AAAA-MM")
    anio = ano_fiscal.strip() if ano_fiscal and ano_fiscal.strip() else None
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
        datos = DatosArchivo(nombre=nombre, sha256=sha256, tamano_bytes=tamano)
        anual_mzt = None
        try:
            if es_budget_anual_mzt(temporal):
                formato_texto = "budget_mzt"
                lineas_estructura = RepositorioReporte(db, contexto.hotel_id).lineas(estructura.id)
                anual_mzt = alinear_con_lineas(
                    leer_budget_anual(temporal),
                    [
                        (x.fila_origen, x.descripcion)
                        for x in lineas_estructura
                        if x.tipo != "seccion"
                    ],
                    {x.fila_origen for x in lineas_estructura if x.tipo == "detalle"},
                )
                mensuales = None
                valores: dict[int, ValoresFila] = {}
            else:
                formato = detectar_formato(temporal).formato
                formato_texto = formato.value
                if formato is Formato.MZT:
                    mensuales = leer_valores_mensuales_mzt(leer_hojas_mzt(temporal))
                    valores = {}
                else:
                    mensuales = None
                    valores = leer_variance_valores(temporal)
        except ValueError as e:
            rechazar(str(e), 422)
            raise HTTPException(status_code=422, detail=str(e)) from None
        except Exception:
            log.exception("No se pudo leer el libro del Variance")
            rechazar("No se pudo leer el libro", 422)
            raise HTTPException(status_code=422, detail="No se pudo leer el libro") from None

        if anual_mzt is not None:
            resultado = importar_budget_mensual(
                db,
                organizacion_id=contexto.organizacion_id,
                hotel_id=contexto.hotel_id,
                usuario_id=contexto.principal.usuario_id,
                version_estructura=estructura,
                por_periodo=anual_mzt.por_periodo,
                anual=anual_mzt.anual,
                archivo=datos,
                ano_fiscal=anio or anual_mzt.ano_fiscal,
                confirmar_reemplazo=confirmar_reemplazo,
            )
            resultado.avisos = [*anual_mzt.avisos, *resultado.avisos]
        elif mensuales is not None:
            if not mensuales.periodos:
                rechazar("El archivo no trae meses con Budget", 422)
                raise HTTPException(status_code=422, detail="El archivo no trae meses con Budget")
            resultado = importar_budget_mensual(
                db,
                organizacion_id=contexto.organizacion_id,
                hotel_id=contexto.hotel_id,
                usuario_id=contexto.principal.usuario_id,
                version_estructura=estructura,
                por_periodo=mensuales.por_periodo,
                archivo=datos,
                ano_fiscal=anio or etiqueta_ano_fiscal(mensuales.periodos[-1]),
                filas_con_cuentas={v.fila_origen for v in leer_variance(temporal).mapeo.vinculos},
                confirmar_reemplazo=confirmar_reemplazo,
            )
        else:
            if periodo_corte is None:
                rechazar("Falta el periodo de corte", 422)
                raise HTTPException(
                    status_code=422, detail="Indica el periodo de corte (AAAA-MM) de este formato"
                )
            resultado = importar_budget(
                db,
                organizacion_id=contexto.organizacion_id,
                hotel_id=contexto.hotel_id,
                usuario_id=contexto.principal.usuario_id,
                version_estructura=estructura,
                valores=valores,
                archivo=datos,
                periodo_corte=periodo_corte,
                ano_fiscal=anio or etiqueta_ano_fiscal(periodo_corte),
                confirmar_reemplazo=confirmar_reemplazo,
            )
        db.commit()
        cuerpo: dict[str, object] = {
            "resolucion": resultado.resolucion.value,
            "motivos": resultado.motivos,
            "avisos": resultado.avisos,
            "formato": formato_texto,
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


# --- Edición en pantalla ----------------------------------------------------------------------


class CeldaEdicion(BaseModel):
    periodo: str
    budget: Decimal | None
    actual: Decimal | None
    actual_origen: (
        str | None
    )  # excel | manual: cómo llegó el Actual capturado (None: sale de cuentas)


class LineaEdicionSalida(BaseModel):
    linea_id: int
    orden: int
    tipo: str
    nivel: int
    seccion_id: int | None
    codigo_corporativo: str | None
    descripcion: str
    editable: bool  # el Budget se puede escribir
    actual_editable: bool  # el Actual se captura a mano (no sale de cuentas ni de un total)
    meses: list[CeldaEdicion]


class ComponenteEdicion(BaseModel):
    linea_id: int
    signo: int  # +1 o -1
    factor: Decimal  # 1, o p. ej. 0.16 en una línea que es el 16 % de otra


class ReglaEdicion(BaseModel):
    linea_id: int
    componentes: list[ComponenteEdicion]


class SeccionEdicion(BaseModel):
    id: int
    descripcion: str


class VistaEdicionSalida(BaseModel):
    ano_fiscal: str
    periodos: list[str]
    version: VersionPlanSalida | None
    secciones: list[SeccionEdicion]
    lineas: list[LineaEdicionSalida]
    reglas: list[ReglaEdicion]
    advertencias: list[str]


class CambioEntrada(BaseModel):
    linea_id: int = Field(ge=1, le=ID_MAX)
    periodo: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    importe: Decimal = Field(allow_inf_nan=False, max_digits=20, decimal_places=6)


class VersionDesdeCambios(BaseModel):
    ano_fiscal: str = Field(pattern=r"^20\d{2}(/\d{2})?$")
    base_version_id: int | None = Field(default=None, ge=1, le=ID_MAX)
    cambios: list[CambioEntrada] = Field(min_length=1, max_length=20_000)


RESPUESTAS_EDICION: dict[int | str, dict[str, object]] = {
    404: {"description": "Hotel o año fiscal no encontrado (o sin acceso)"},
    409: {"description": "Falta la estructura o el mapeo, o la versión base ya no es la vigente"},
    422: {"description": "Un cambio no es válido (línea, mes o importe)"},
}


@router.get(
    "/hoteles/{hotel_id}/budget/edicion",
    response_model=VistaEdicionSalida,
    responses=RESPUESTAS_EDICION,
)
def ver_edicion(
    contexto: LecturaOCaptura,
    ano_fiscal: Annotated[str, Query(pattern=r"^20\d{2}(/\d{2})?$", description="Ej. 2026/27")],
    version_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    db: Session = Depends(get_db),
) -> VistaEdicionSalida:
    """El Budget (mes a mes) y el Actual de referencia de cada línea, para editarlo."""
    try:
        vista = vista_edicion(
            db, hotel_id=contexto.hotel_id, ano_fiscal=ano_fiscal, version_id=version_id
        )
    except LookupError as e:
        raise HTTPException(status_code=409, detail=str(e.args[0])) from None
    except EdicionInvalida as e:  # un año fiscal que no existe (p. ej. 2026/99): no hay recurso
        raise HTTPException(status_code=404, detail=str(e)) from None
    return VistaEdicionSalida(
        ano_fiscal=vista.ano_fiscal,
        periodos=vista.periodos,
        version=_version(vista.version) if vista.version else None,
        secciones=[SeccionEdicion(id=x.id, descripcion=x.descripcion) for x in vista.secciones],
        lineas=[
            LineaEdicionSalida(
                linea_id=x.linea.id,
                orden=x.linea.orden,
                tipo=x.linea.tipo,
                nivel=x.linea.nivel,
                seccion_id=x.linea.seccion_id,
                codigo_corporativo=x.linea.codigo_corporativo,
                descripcion=x.linea.descripcion,
                editable=x.editable,
                actual_editable=x.actual_editable,
                meses=[
                    CeldaEdicion(
                        periodo=p,
                        budget=x.budget[p],
                        actual=x.actual[p],
                        actual_origen=x.origen_actual.get(p),
                    )
                    for p in vista.periodos
                ],
            )
            for x in vista.lineas
        ],
        reglas=[
            ReglaEdicion(
                linea_id=total,
                componentes=[
                    ComponenteEdicion(linea_id=c, signo=1 if s > 0 else -1, factor=abs(Decimal(s)))
                    for c, s in componentes
                ],
            )
            for total, componentes in vista.reglas.items()
        ],
        advertencias=vista.advertencias,
    )


@router.post(
    "/hoteles/{hotel_id}/budget/versiones",
    status_code=201,
    responses=RESPUESTAS_EDICION,
)
def guardar_edicion(
    entrada: VersionDesdeCambios,
    contexto: Importacion,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Guarda una versión nueva del Budget con los cambios; la anterior queda como `reemplazada`."""
    try:
        resultado = crear_version_desde_cambios(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ano_fiscal=entrada.ano_fiscal,
            base_version_id=entrada.base_version_id,
            cambios=[CambioBudget(c.linea_id, c.periodo, c.importe) for c in entrada.cambios],
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e.args[0])) from None
    except BaseDesactualizada as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from None
    except EdicionInvalida as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from None
    db.commit()
    return JSONResponse(
        status_code=_HTTP[resultado.resolucion],
        content={
            "resolucion": resultado.resolucion.value,
            "motivos": resultado.motivos,
            "avisos": resultado.avisos,
            "version": _version(resultado.version).model_dump(mode="json")
            if resultado.version
            else None,
        },
    )


class ValorCapturadoEntrada(BaseModel):
    linea_id: int = Field(ge=1, le=ID_MAX)
    periodo: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    # None borra el valor capturado
    importe: Decimal | None = Field(
        default=None, allow_inf_nan=False, max_digits=20, decimal_places=6
    )


class CapturaEntrada(BaseModel):
    valores: list[ValorCapturadoEntrada] = Field(min_length=1, max_length=2_000)


class CapturaSalida(BaseModel):
    guardados: int


@router.put(
    "/hoteles/{hotel_id}/budget/capturados",
    response_model=CapturaSalida,
    responses={
        409: {
            "description": "Primero hay que importar la estructura del reporte y aprobar el mapeo"
        },
        422: {"description": "Una línea o un importe no se puede capturar"},
    },
)
def capturar_actual(
    entrada: CapturaEntrada,
    contexto: Importacion,
    db: Session = Depends(get_db),
) -> CapturaSalida:
    """Guarda el Actual capturado a mano (p. ej. el tipo de cambio de cada mes); vacío lo borra."""
    try:
        n = capturar_actuales(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            valores=[ValorEntrada(v.linea_id, v.periodo, v.importe) for v in entrada.valores],
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e.args[0])) from None
    except CapturaInvalida as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from None
    db.commit()
    return CapturaSalida(guardados=n)
