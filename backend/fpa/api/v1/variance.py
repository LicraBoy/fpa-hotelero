"""Variance de un periodo (Fase 3.6): Actual, Budget, Variance y Variance % por línea.

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Solo lectura.
Los importes salen redondeados a centavos y los porcentajes a 6 decimales; el cálculo interno es
exacto (el redondeo es solo de presentación).
"""

import re
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_REPORTE
from fpa.api.v1.tipos import ID_MAX
from fpa.calculo.motor import Cifras
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.modelos.organizacion import Hotel
from fpa.modelos.reporte import LineaReporte
from fpa.servicios.acceso_secciones import exigir_acceso_completo, restriccion
from fpa.servicios.auditoria import auditar
from fpa.servicios.cierre import estado_de, versiones_congeladas
from fpa.servicios.comentarios_excel import comentarios_por_linea
from fpa.servicios.exportar_variance import generar_excel, nombre_de_archivo
from fpa.servicios.reportes import cache_variance
from fpa.servicios.variance import PlanIncompatible, ReporteVariance, calcular_variance

router = APIRouter(tags=["variance"])
_RE_PERIODO = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
CENTAVO = Decimal("0.01")
MICRO = Decimal("0.000001")

TipoLineaFiltro = Literal["detalle", "subtotal", "total", "informativa"]

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
    capturada: bool  # línea informativa con Actual capturado (mes), p. ej. el tipo de cambio
    mes: CifrasSalida
    ytd: CifrasSalida
    anual: CifrasSalida


class SeccionSalida(BaseModel):
    id: int
    descripcion: str
    linea_total_id: int | None


class VarianceSalida(BaseModel):
    periodo: str
    ano_fiscal: str
    version_mapeo_id: int
    version_plan_id: int | None
    periodos_ytd: list[str]
    periodos_sin_datos: list[str]
    advertencias: list[str]
    secciones: list[SeccionSalida]
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


def _pasa(
    linea: LineaReporte | LineaVarianceSalida,
    seccion_id: int | None,
    tipos: Sequence[str] | None,
    q: str | None,
) -> bool:
    if seccion_id is not None and linea.seccion_id != seccion_id:
        return False
    if tipos and linea.tipo not in tipos:
        return False
    return not q or q.strip().lower() in linea.descripcion.lower()


@router.get(
    "/hoteles/{hotel_id}/variance",
    response_model=VarianceSalida,
    responses=RESPUESTAS_REPORTE,
)
def variance(
    contexto: Lectura,
    periodo: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", description="AAAA-MM")],
    version_mapeo_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    version_plan_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    seccion_id: Annotated[
        int | None, Query(ge=1, le=ID_MAX, description="Solo las líneas de esa sección")
    ] = None,
    tipo: Annotated[
        list[TipoLineaFiltro] | None,
        Query(description="Solo líneas de estos tipos (repetible)"),
    ] = None,
    q: Annotated[
        str | None,
        Query(max_length=100, description="Texto contenido en la descripción de la línea"),
    ] = None,
    db: Session = Depends(get_db),
) -> Response:
    """Variance del periodo con el mapeo aprobado y el Budget vigente (o las indicadas).

    El reporte completo se guarda en la caché del servidor (se invalida al cargar o aprobar); los
    filtros se aplican sobre él. La cabecera `X-Cache` dice si salió de la caché (`hit`) o se
    calculó (`miss`); el resultado es el mismo.
    """
    if not _RE_PERIODO.match(periodo):
        raise HTTPException(status_code=422, detail="El periodo debe ser AAAA-MM")
    if version_mapeo_id is None and version_plan_id is None:
        # un periodo aprobado o bloqueado se calcula con las versiones con que se aprobó
        congeladas = versiones_congeladas(db, contexto.hotel_id, periodo)
        if congeladas is not None:
            version_mapeo_id, version_plan_id = congeladas
    clave = cache_variance.clave(
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        version_mapeo_id=version_mapeo_id,
        version_plan_id=version_plan_id,
        periodo=periodo,
    )
    guardado = cache_variance.obtener(clave)
    if guardado is None:
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
        modelo = _salida(r)
        guardado = (modelo, modelo.model_dump_json().encode())
        cache_variance.guardar(clave, guardado)
        estado = "miss"
    else:
        estado = "hit"
    modelo, crudo = guardado
    permitidas = restriccion(contexto)
    if permitidas is not None:
        # Responsable de departamento: solo sus secciones (sin avisos que hablen de las demás)
        ids = {x.id for x in modelo.secciones if x.descripcion in permitidas}
        modelo = modelo.model_copy(
            update={
                "secciones": [x for x in modelo.secciones if x.id in ids],
                "lineas": [x for x in modelo.lineas if x.seccion_id in ids],
                "advertencias": [],
            }
        )
        crudo = modelo.model_dump_json().encode()
    if seccion_id is None and not tipo and not q:
        contenido = crudo
    else:
        filtrado = modelo.model_copy(
            update={"lineas": [x for x in modelo.lineas if _pasa(x, seccion_id, tipo, q)]}
        )
        contenido = filtrado.model_dump_json().encode()
    return Response(content=contenido, media_type="application/json", headers={"X-Cache": estado})


def _salida(r: ReporteVariance) -> VarianceSalida:
    return VarianceSalida(
        periodo=r.periodo,
        ano_fiscal=r.ano_fiscal,
        version_mapeo_id=r.version_mapeo_id,
        version_plan_id=r.version_plan_id,
        periodos_ytd=r.periodos_ytd,
        periodos_sin_datos=r.periodos_sin_datos,
        advertencias=r.advertencias,
        secciones=[SeccionSalida(**vars(x)) for x in r.secciones],
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
                capturada=x.id in r.capturadas,
                mes=_cifras(r.resultado[x.id].mes),
                ytd=_cifras(r.resultado[x.id].ytd),
                anual=_cifras(r.resultado[x.id].anual),
            )
            for x in r.lineas
        ],
    )


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/hoteles/{hotel_id}/variance/exportar",
    responses={
        **RESPUESTAS_REPORTE,
        200: {
            "description": "Libro de Excel con el reporte (mismo orden y bloques que la pantalla)",
            "content": {XLSX: {"schema": {"type": "string", "format": "binary"}}},
        },
    },
    response_class=Response,
)
def exportar(
    contexto: Lectura,
    periodo: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", description="AAAA-MM")],
    version_mapeo_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    version_plan_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    seccion_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    tipo: Annotated[list[TipoLineaFiltro] | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    db: Session = Depends(get_db),
) -> Response:
    """Descarga el Variance completo en Excel, con fórmulas vivas; queda en la bitácora.

    Los filtros de la pantalla (`seccion_id`, `tipo`, `q`) se aceptan por compatibilidad pero se
    ignoran: las fórmulas de los totales necesitan todas sus partes. Quien solo tiene asignadas
    algunas secciones no puede exportar (el libro trae todo el reporte).
    """
    exigir_acceso_completo(contexto)
    if version_mapeo_id is None and version_plan_id is None:
        congeladas = versiones_congeladas(db, contexto.hotel_id, periodo)
        if congeladas is not None:
            version_mapeo_id, version_plan_id = congeladas
    try:
        r = calcular_variance(
            db,
            hotel_id=contexto.hotel_id,
            periodo=periodo,
            version_mapeo_id=version_mapeo_id,
            version_plan_id=version_plan_id,
            con_insumos=True,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except PlanIncompatible as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    lineas = r.lineas
    hotel = db.get(Hotel, contexto.hotel_id)
    contenido = generar_excel(
        hotel=hotel.nombre if hotel else f"Hotel {contexto.hotel_id}",
        periodo=r.periodo,
        ano_fiscal=r.ano_fiscal,
        lineas=lineas,
        secciones=r.secciones,
        resultado=r.resultado,
        capturadas=r.capturadas,
        advertencias=r.advertencias,
        version_mapeo=r.version_mapeo_id,
        version_budget=r.version_plan_id,
        periodos_ytd=r.periodos_ytd,
        insumos=r.insumos,
        estado_cierre=estado_de(db, contexto.hotel_id, r.periodo),
        comentarios=(
            comentarios_por_linea(db, contexto.hotel_id, r.periodo)
            if contexto.principal.puede(contexto.hotel_id, Permiso.COMENTARIO_LEER)
            else None
        ),
    )
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="variance.exportado",
        entidad="variance",
        detalle={"periodo": periodo, "n_lineas": len(lineas), "bytes": len(contenido)},
    )
    db.commit()
    return Response(
        content=contenido,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre_de_archivo(periodo)}"',
            "Cache-Control": "no-store",
        },
    )
