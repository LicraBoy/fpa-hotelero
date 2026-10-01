"""Variance de un periodo: junta Actual, Budget, mapeo y reglas y llama al motor puro."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, etiqueta_ano_fiscal
from fpa.calculo.motor import LineaVariance, armar_variance
from fpa.calculo.variance import Convencion, LineaParaConvencion, deducir_convenciones
from fpa.modelos.plan import TIPO_BUDGET, VersionPlan
from fpa.modelos.reporte import LineaReporte
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.plan import RepositorioPlan
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.actual import actual_del_periodo, actual_ytd_del_periodo, version_de_mapeo
from fpa.servicios.reglas_suma import reglas_como_mapa


class PlanIncompatible(ValueError):
    """El Budget pertenece a otra estructura del reporte que el mapeo."""


@dataclass(frozen=True)
class SeccionReporte:
    """Una sección del reporte y la línea que la totaliza (si tiene)."""

    id: int
    descripcion: str
    linea_total_id: int | None


@dataclass
class ReporteVariance:
    hotel_id: int
    periodo: str
    ano_fiscal: str
    version_mapeo_id: int
    version_plan_id: int | None
    periodos_ytd: list[str]
    periodos_sin_datos: list[str]
    lineas: list[LineaReporte]
    resultado: dict[int, LineaVariance]
    secciones: list[SeccionReporte] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


def _plan(
    db: Session, hotel_id: int, periodo: str, version_plan_id: int | None
) -> VersionPlan | None:
    repo = RepositorioPlan(db, hotel_id)
    if version_plan_id is not None:
        version = repo.obtener(version_plan_id)
        if version is None:
            raise LookupError("Versión de Budget no encontrada")
        return version
    return repo.vigente(TIPO_BUDGET, etiqueta_ano_fiscal(periodo))


def secciones_del_reporte(lineas: list[LineaReporte]) -> list[SeccionReporte]:
    """Secciones en orden; su línea de total es el último `total` de la sección (o subtotal)."""
    salida: list[SeccionReporte] = []
    for seccion in (x for x in lineas if x.tipo == "seccion"):
        propias = [x for x in lineas if x.seccion_id == seccion.id]
        totales = [x for x in propias if x.tipo == "total"] or [
            x for x in propias if x.tipo == "subtotal"
        ]
        salida.append(
            SeccionReporte(seccion.id, seccion.descripcion, totales[-1].id if totales else None)
        )
    return salida


def calcular_variance(
    db: Session,
    *,
    hotel_id: int,
    periodo: str,
    version_mapeo_id: int | None = None,
    version_plan_id: int | None = None,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
    excepciones: dict[int, Convencion] | None = None,
) -> ReporteVariance:
    """Reporte Variance del `periodo` (`AAAA-MM`) para un hotel.

    Usa el mapeo aprobado y el Budget vigente del año fiscal, salvo que se indiquen versiones.
    Lanza `LookupError` si falta el mapeo o la versión pedida, y `PlanIncompatible` si el Budget y
    el mapeo usan estructuras distintas. Un mes sin movimientos cargados se informa, no se oculta.
    """
    mapeo = version_de_mapeo(db, hotel_id, version_mapeo_id)
    plan = _plan(db, hotel_id, periodo, version_plan_id)
    if plan is not None and plan.version_estructura_id != mapeo.version_estructura_id:
        raise PlanIncompatible(
            "El Budget y el mapeo usan estructuras del reporte distintas; reimporta el Budget"
        )

    reportes = RepositorioReporte(db, hotel_id)
    todas = reportes.lineas(mapeo.version_estructura_id)
    lineas = [x for x in todas if x.tipo != "seccion"]
    secciones = secciones_del_reporte(todas)
    reglas = reglas_como_mapa(db, hotel_id, mapeo.version_estructura_id)

    mes = actual_del_periodo(db, hotel_id=hotel_id, periodo=periodo, version_mapeo_id=mapeo.id)
    ytd = actual_ytd_del_periodo(
        db, hotel_id=hotel_id, periodo=periodo, version_mapeo_id=mapeo.id, mes_inicio=mes_inicio
    )

    cuentas: dict[int, list[tuple[str, int]]] = {}
    for v in RepositorioMapeo(db, hotel_id).vinculos(mapeo.id):
        cuentas.setdefault(v.linea_id, []).append((v.cuenta_codigo, v.signo))
    convenciones = deducir_convenciones(
        [
            LineaParaConvencion(x.id, x.tipo, x.seccion_id)
            for x in reportes.lineas(mapeo.version_estructura_id)
        ],
        cuentas,
        reglas,
        excepciones,
    )

    advertencias: list[str] = []
    b_mes: dict[int, Decimal] | None = None
    b_ytd: dict[int, Decimal] | None = None
    b_anual: dict[int, Decimal] | None = None
    if plan is None:
        advertencias.append("No hay Budget para este año fiscal: no se calcula el Variance")
    else:
        filas = RepositorioPlan(db, hotel_id).lineas(plan.id)
        b_anual = {x.linea_id: x.anual for x in filas if x.anual is not None}
        if plan.periodo_corte == periodo:
            b_mes = {x.linea_id: x.mes for x in filas if x.mes is not None}
            b_ytd = {x.linea_id: x.ytd for x in filas if x.ytd is not None}
        else:
            advertencias.append(
                f"El Budget cargado es del corte {plan.periodo_corte}: el Budget del mes y del "
                f"acumulado de {periodo} no está disponible (solo el anual)"
            )
    excluidas = RepositorioMapeo(db, hotel_id).excluidas(mapeo.id)
    if excluidas:
        codigos = ", ".join(e.cuenta_codigo for e in excluidas[:5])
        advertencias.append(
            f"El mapeo (versión {mapeo.numero}) deja fuera a propósito {len(excluidas)} cuentas "
            f"({codigos}): sus movimientos no entran al reporte"
        )
    if ytd.sin_datos:
        advertencias.append(
            "El acumulado está incompleto: faltan movimientos de " + ", ".join(ytd.sin_datos)
        )

    resultado = armar_variance(
        [x.id for x in lineas], reglas, convenciones, mes, ytd.por_linea, b_mes, b_ytd, b_anual
    )
    return ReporteVariance(
        hotel_id=hotel_id,
        periodo=periodo,
        ano_fiscal=etiqueta_ano_fiscal(periodo, mes_inicio),
        version_mapeo_id=mapeo.id,
        version_plan_id=plan.id if plan else None,
        periodos_ytd=ytd.periodos,
        periodos_sin_datos=ytd.sin_datos,
        lineas=lineas,
        resultado=resultado,
        secciones=secciones,
        advertencias=advertencias,
    )
