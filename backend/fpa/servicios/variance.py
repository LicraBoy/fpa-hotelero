"""Variance de un periodo: junta Actual, Budget, mapeo y reglas y llama al motor puro."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, etiqueta_ano_fiscal, periodos_ytd
from fpa.calculo.motor import Cifras, LineaVariance, armar_variance
from fpa.calculo.variance import Convencion, LineaParaConvencion, deducir_convenciones
from fpa.modelos.plan import TIPO_BUDGET, LineaPlanMensual, VersionPlan
from fpa.modelos.reporte import LineaReporte
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.plan import RepositorioPlan
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.actual import actual_del_periodo, actual_ytd_del_periodo, version_de_mapeo
from fpa.servicios.convenciones_linea import convenciones_por_bloque
from fpa.servicios.reglas_suma import lineas_aditivas, reglas_como_mapa
from fpa.servicios.validacion_mapeo import validar_mapeo
from fpa.servicios.valores_capturados import lineas_capturables

CERO = Decimal("0")


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
    capturadas: frozenset[int] = frozenset()  # líneas informativas con Actual capturado (mes)
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


def _budget_mensual(
    filas: list[LineaPlanMensual],
    periodo: str,
    ytd: list[str],
    sin_acumular: set[int],
    advertencias: list[str],
) -> tuple[dict[int, Decimal] | None, dict[int, Decimal] | None]:
    """Budget del mes y del acumulado (suma de los meses del año fiscal) de los meses cargados."""
    por_periodo: dict[str, dict[int, Decimal]] = {}
    for f in filas:
        por_periodo.setdefault(f.periodo, {})[f.linea_id] = f.importe
    b_mes = por_periodo.get(periodo)
    if b_mes is None:
        advertencias.append(
            f"No hay Budget para {periodo} (el Budget cargado trae "
            f"{', '.join(sorted(por_periodo))}): Presupuesto, Variación y % quedan en «—». "
            "Captúralo en la pestaña Budget o importa el Excel de Contraloría con ese mes"
        )
        return None, None
    faltan = [p for p in ytd if p not in por_periodo]
    if faltan:
        advertencias.append(
            "El Budget del acumulado no se calcula porque falta el Budget de "
            + ", ".join(faltan)
            + " (el acumulado suma todos los meses del año fiscal hasta este)"
        )
        return b_mes, None
    b_ytd: dict[int, Decimal] = {}
    for p in ytd:
        for linea, importe in por_periodo[p].items():
            b_ytd[linea] = b_ytd.get(linea, CERO) + importe
    for linea in sin_acumular:  # un tipo de cambio no se suma: su acumulado es el promedio
        if linea in b_ytd:
            b_ytd[linea] = b_ytd[linea] / len(ytd)
    return b_mes, b_ytd


def _sin_variacion(linea: LineaVariance, *, mes: bool, acumulado: bool) -> LineaVariance:
    """Quita la Variación y el % de los bloques indicados (el Actual no existe, no es 0)."""

    def sin(c: Cifras, quitar: bool) -> Cifras:
        return Cifras(c.actual, c.budget, None, None) if quitar else c

    return LineaVariance(
        linea_id=linea.linea_id,
        convencion=linea.convencion,
        mes=sin(linea.mes, mes),
        ytd=sin(linea.ytd, acumulado),
        anual=sin(linea.anual, acumulado),
    )


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
    aditivas = lineas_aditivas(reglas, set(cuentas))
    detalle_con_regla = frozenset(x.id for x in lineas if x.tipo == "detalle" and x.id in reglas)
    por_bloque, compuestas = convenciones_por_bloque(db, hotel_id, mapeo.version_estructura_id)
    # lo escrito en el Excel (mes) manda sobre lo deducido; una excepción pedida a mano, sobre todo
    excepciones = {**por_bloque["mes"], **(excepciones or {})}
    convenciones = deducir_convenciones(
        [
            LineaParaConvencion(x.id, x.tipo, x.seccion_id)
            for x in reportes.lineas(mapeo.version_estructura_id)
        ],
        cuentas,
        reglas,
        excepciones,
    )

    # Un tipo de cambio no es la suma de sus meses: las líneas informativas que ningún total suma
    # (a diferencia de las del resumen, que sí son dinero) no se acumulan.
    sumadas = {c for componentes in reglas.values() for c, _ in componentes}
    no_se_acumulan = {x.id for x in lineas if x.tipo == "informativa" and x.id not in sumadas}
    advertencias: list[str] = []
    b_mes: dict[int, Decimal] | None = None
    b_ytd: dict[int, Decimal] | None = None
    b_anual: dict[int, Decimal] | None = None
    if plan is None:
        advertencias.append("No hay Budget para este año fiscal: no se calcula el Variance")
    else:
        repo_plan = RepositorioPlan(db, hotel_id)
        filas = repo_plan.lineas(plan.id)
        b_anual = {x.linea_id: x.anual for x in filas if x.anual is not None} or None
        mensuales = repo_plan.mensuales(plan.id)
        if mensuales:
            b_mes, b_ytd = _budget_mensual(
                mensuales, periodo, periodos_ytd(periodo, mes_inicio), no_se_acumulan, advertencias
            )
        elif plan.periodo_corte == periodo:
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
    sin_linea = validar_mapeo(
        db, hotel_id=hotel_id, version_mapeo_id=mapeo.id, periodo=periodo
    ).sin_mapear
    if sin_linea:
        mayores = sorted(sin_linea, key=lambda c: abs(c.neto), reverse=True)[:5]
        total = sum((abs(c.neto) for c in sin_linea), CERO)
        detalle = ", ".join(f"{c.cuenta_codigo} ({abs(c.neto):,.2f})" for c in mayores)
        advertencias.append(
            f"{len(sin_linea)} cuentas con movimiento en {periodo} no están en ninguna línea del "
            f"reporte y no aparecen en él (importe {total:,.2f}): {detalle}"
            + ("…" if len(sin_linea) > len(mayores) else "")
        )
    if ytd.sin_datos:
        advertencias.append(
            "El acumulado está incompleto: faltan movimientos de " + ", ".join(ytd.sin_datos)
        )

    # Actual capturado (lo trae el Excel o se escribe a mano): solo líneas sin cuentas ni regla de
    # suma. El acumulado suma los meses capturados; en las que no se acumulan (el tipo de cambio),
    # es el promedio de los meses capturados.
    periodos_del_ytd = periodos_ytd(periodo, mes_inicio)
    capturados: dict[int, Decimal] = {}
    capturados_ytd: dict[int, Decimal] = {}
    meses_capturados: dict[int, int] = {}
    for x in RepositorioPlan(db, hotel_id).capturados(
        mapeo.version_estructura_id, periodos_del_ytd
    ):
        if x.linea_id in cuentas or x.linea_id in reglas:
            continue
        if x.periodo == periodo:
            capturados[x.linea_id] = x.importe
        capturados_ytd[x.linea_id] = capturados_ytd.get(x.linea_id, CERO) + x.importe
        meses_capturados[x.linea_id] = meses_capturados.get(x.linea_id, 0) + 1
    for linea_id in no_se_acumulan:
        if linea_id in capturados_ytd:
            capturados_ytd[linea_id] = capturados_ytd[linea_id] / meses_capturados[linea_id]
    capturables = lineas_capturables(db, hotel_id, mapeo.id)
    sin_captura = [x for x in lineas if x.id in capturables and x.id not in capturados]
    if sin_captura:
        nombres = ", ".join(x.descripcion.strip() for x in sin_captura[:3])
        advertencias.append(
            f"{len(sin_captura)} líneas sin cuentas no tienen Actual capturado en {periodo} "
            f"(se toman como 0): {nombres}"
            + ("…" if len(sin_captura) > 3 else "")
            + ". Se escribe en la pestaña Budget (fila de la línea, columna Actual)"
        )
    mes = {**mes, **capturados}
    acumulado = {**ytd.por_linea, **capturados_ytd}

    resultado = armar_variance(
        [x.id for x in lineas],
        reglas,
        convenciones,
        mes,
        acumulado,
        b_mes,
        b_ytd,
        b_anual,
        aditivas,
        detalle_con_regla,
        por_bloque,
        compuestas,
    )
    # Un tipo de cambio sin capturar no tiene Variación: un Actual en 0 la inventaría
    for linea_id in no_se_acumulan:
        resultado[linea_id] = _sin_variacion(
            resultado[linea_id],
            mes=linea_id not in capturados,
            acumulado=linea_id not in meses_capturados,
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
        capturadas=frozenset(capturados),
        advertencias=advertencias,
    )
