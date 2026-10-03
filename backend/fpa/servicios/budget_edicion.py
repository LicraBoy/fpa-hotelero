"""Edición del Budget en pantalla: ver el Budget y el Actual mes a mes y guardar una versión nueva.

Una versión del Budget **nunca se edita** (ADR 0003): guardar crea una versión nueva a partir de la
base (copia lo que ya había, aplica los cambios) y deja la anterior como `reemplazada`.

- Solo se editan líneas de **detalle sin regla de suma**: los totales y subtotales salen siempre de
  sus reglas (`calculo/totales.py`), también en el Budget, y por eso no se guardan.
- El Actual que se muestra al lado es de **referencia** (viene de los movimientos cargados y del
  mapeo aprobado): un mes sin movimientos cargados es `None`, nunca un cero.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import (
    MES_INICIO_POR_DEFECTO,
    etiqueta_ano_fiscal,
    periodos_del_ano_fiscal,
)
from fpa.calculo.totales import completar_con_totales
from fpa.ingesta.variance_mzt import ValoresMes
from fpa.modelos.plan import TIPO_BUDGET, VIGENTE, VersionPlan
from fpa.modelos.reporte import LineaReporte, VersionEstructuraReporte
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.plan import RepositorioPlan
from fpa.repositorios.reporte import RepositorioReporte
from fpa.repositorios.saldos import RepositorioSaldos
from fpa.servicios.actual import actual_del_periodo, version_de_mapeo
from fpa.servicios.budget import ResultadoImportacionBudget, importar_budget_mensual
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.reglas_suma import lineas_aditivas, reglas_como_mapa
from fpa.servicios.valores_capturados import lineas_capturables

IMPORTE_MAXIMO = Decimal("1000000000000")  # un billón: más que cualquier presupuesto de un hotel
NOMBRE_EDICION = "Edición en pantalla"


class EdicionInvalida(ValueError):
    """Un cambio no se puede aplicar (línea, mes o importe no válidos)."""


class BaseDesactualizada(ValueError):
    """La versión sobre la que se editó ya no es la vigente (alguien guardó otra antes)."""


@dataclass(frozen=True)
class CambioBudget:
    linea_id: int
    periodo: str
    importe: Decimal


@dataclass
class LineaEdicion:
    linea: LineaReporte
    editable: bool  # el Budget de la línea se puede escribir
    budget: dict[str, Decimal | None]
    actual: dict[str, Decimal | None]
    actual_editable: bool = False  # el Actual se captura a mano (no sale de cuentas ni de un total)
    origen_actual: dict[str, str | None] = field(default_factory=dict)  # excel | manual por mes


@dataclass
class VistaEdicion:
    ano_fiscal: str
    periodos: list[str]
    version: VersionPlan | None
    version_estructura_id: int
    lineas: list[LineaEdicion]
    reglas: Mapping[int, Sequence[tuple[int, int | Decimal]]]
    secciones: list[LineaReporte]
    advertencias: list[str] = field(default_factory=list)


def periodos_de_ano_fiscal(ano_fiscal: str, mes_inicio: int = MES_INICIO_POR_DEFECTO) -> list[str]:
    """`2026/27` -> los 12 meses de 2026-07 a 2027-06 (`2026` si el año fiscal es el calendario)."""
    if not ano_fiscal[:4].isdigit():
        raise EdicionInvalida(f"Año fiscal inválido {ano_fiscal!r}")
    inicio = f"{int(ano_fiscal[:4]):04d}-{mes_inicio:02d}"
    if etiqueta_ano_fiscal(inicio, mes_inicio) != ano_fiscal:
        raise EdicionInvalida(f"Año fiscal inválido {ano_fiscal!r}")
    return periodos_del_ano_fiscal(inicio, mes_inicio)


def _estructura_vigente(db: Session, hotel_id: int) -> VersionEstructuraReporte:
    estructura = RepositorioReporte(db, hotel_id).vigente()
    if estructura is None:
        raise LookupError("Primero importa la estructura del reporte (reporte/importar)")
    return estructura


def _version_base(
    db: Session, hotel_id: int, ano_fiscal: str, version_id: int | None
) -> VersionPlan | None:
    repo = RepositorioPlan(db, hotel_id)
    if version_id is None:
        return repo.vigente(TIPO_BUDGET, ano_fiscal)
    version = repo.obtener(version_id)
    if version is None:
        raise LookupError("Versión de Budget no encontrada")
    if version.ano_fiscal != ano_fiscal:
        raise EdicionInvalida("La versión no es de ese año fiscal")
    return version


def vista_edicion(
    db: Session,
    *,
    hotel_id: int,
    ano_fiscal: str,
    version_id: int | None = None,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> VistaEdicion:
    """Líneas del reporte con su Budget (de la versión) y su Actual de referencia, mes a mes."""
    periodos = periodos_de_ano_fiscal(ano_fiscal, mes_inicio)
    estructura = _estructura_vigente(db, hotel_id)
    mapeo = version_de_mapeo(db, hotel_id, None)
    version = _version_base(db, hotel_id, ano_fiscal, version_id)
    advertencias: list[str] = []
    if version is not None and version.version_estructura_id != estructura.id:
        advertencias.append(
            "El Budget es de otra estructura del reporte: no se muestra; guarda uno nuevo o "
            "reimporta el Budget"
        )
        version = None

    todas = RepositorioReporte(db, hotel_id).lineas(estructura.id)
    lineas = [x for x in todas if x.tipo != "seccion"]
    reglas = reglas_como_mapa(db, hotel_id, estructura.id)

    planes = RepositorioPlan(db, hotel_id)
    budget_por_mes: dict[str, dict[int, Decimal]] = {p: {} for p in periodos}
    if version is not None:
        for fila in planes.budget_por_mes(version):
            if fila.periodo in budget_por_mes:
                budget_por_mes[fila.periodo][fila.linea_id] = fila.importe
    cap = planes.capturados(estructura.id, periodos)
    capturados = {(x.linea_id, x.periodo): x.importe for x in cap}
    origenes = {(x.linea_id, x.periodo): x.origen for x in cap}
    capturables = lineas_capturables(db, hotel_id)

    con_cuentas = {v.linea_id for v in RepositorioMapeo(db, hotel_id).vinculos(mapeo.id)}
    aditivas = lineas_aditivas(reglas, con_cuentas)
    # Una línea de detalle con regla (cuentas + líneas, o «16 % de otra») trae su Budget como número
    detalle_ids = {x.id for x in lineas if x.tipo == "detalle"}
    reglas_budget = {k: v for k, v in reglas.items() if k not in detalle_ids}

    con_datos = set(RepositorioSaldos(db, hotel_id).periodos())
    actual_por_mes: dict[str, dict[int, Decimal] | None] = {}
    for p in periodos:
        actual_por_mes[p] = (
            completar_con_totales(
                reglas,
                actual_del_periodo(db, hotel_id=hotel_id, periodo=p, version_mapeo_id=mapeo.id),
                aditivas,
            )
            if p in con_datos
            else None
        )
    budget_completo = {
        p: completar_con_totales(reglas_budget, budget_por_mes[p]) if budget_por_mes[p] else {}
        for p in periodos
    }

    salida: list[LineaEdicion] = []
    for linea in lineas:
        con_regla = linea.id in reglas_budget
        budget: dict[str, Decimal | None] = {}
        actual: dict[str, Decimal | None] = {}
        for p in periodos:
            budget[p] = budget_completo[p].get(linea.id) if budget_completo[p] else None
            mes = actual_por_mes[p]
            if (linea.id, p) in capturados:
                actual[p] = capturados[(linea.id, p)]
            elif linea.tipo == "informativa" and not con_regla:
                actual[p] = None  # un tipo de cambio sin capturar no es un cero
            else:
                actual[p] = None if mes is None else mes.get(linea.id, Decimal(0))
        salida.append(
            LineaEdicion(
                linea,
                linea.tipo in ("detalle", "informativa") and not con_regla,
                budget,
                actual,
                linea.id in capturables,
                {p: origenes.get((linea.id, p)) for p in periodos},
            )
        )
    return VistaEdicion(
        ano_fiscal=ano_fiscal,
        periodos=periodos,
        version=version,
        version_estructura_id=estructura.id,
        lineas=salida,
        reglas=reglas_budget,
        secciones=[x for x in todas if x.tipo == "seccion"],
        advertencias=advertencias,
    )


def _hash_contenido(por_periodo: dict[str, dict[int, ValoresMes]]) -> tuple[str, int]:
    canonico = json.dumps(
        {
            p: {str(f): str(v.budget) for f, v in sorted(filas.items())}
            for p, filas in sorted(por_periodo.items())
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonico).hexdigest(), len(canonico)


def crear_version_desde_cambios(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ano_fiscal: str,
    cambios: list[CambioBudget],
    base_version_id: int | None = None,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> ResultadoImportacionBudget:
    """Guarda una versión nueva del Budget con los `cambios` sobre la base. El llamador hace commit.

    Lanza `LookupError` (sin estructura o base inexistente), `EdicionInvalida` (cambio no válido o
    sin cambios reales) y `BaseDesactualizada` (la base ya no es la vigente).
    """
    periodos = periodos_de_ano_fiscal(ano_fiscal, mes_inicio)
    estructura = _estructura_vigente(db, hotel_id)
    repo = RepositorioPlan(db, hotel_id)
    vigente = repo.vigente(TIPO_BUDGET, ano_fiscal)
    base = _version_base(db, hotel_id, ano_fiscal, base_version_id)
    if base_version_id is not None and (vigente is None or vigente.id != base_version_id):
        raise BaseDesactualizada(
            "Alguien guardó otra versión del Budget mientras editabas: recarga y vuelve a aplicar"
        )
    if base is not None and (base.estado != VIGENTE or base.version_estructura_id != estructura.id):
        raise BaseDesactualizada("El Budget es de otra estructura del reporte: reimporta el Budget")
    if not cambios:
        raise EdicionInvalida("No hay cambios que guardar")

    todas = RepositorioReporte(db, hotel_id).lineas(estructura.id)
    por_id = {x.id: x for x in todas}
    reglas = reglas_como_mapa(db, hotel_id, estructura.id)
    reglas = {k: v for k, v in reglas.items() if por_id[k].tipo != "detalle"}

    por_periodo: dict[str, dict[int, ValoresMes]] = {p: {} for p in periodos}
    previo: dict[tuple[int, str], Decimal] = {}
    if base is not None:
        for fila in repo.budget_por_mes(base):
            linea = por_id.get(fila.linea_id)
            if linea is None or fila.linea_id in reglas or fila.periodo not in por_periodo:
                continue  # un total se recalcula de sus reglas: no se arrastra
            previo[(fila.linea_id, fila.periodo)] = fila.importe
            por_periodo[fila.periodo][linea.fila_origen] = ValoresMes(
                linea.fila_origen, budget=fila.importe
            )

    hubo_cambio = False
    for c in cambios:
        linea = por_id.get(c.linea_id)
        if linea is None:
            raise EdicionInvalida(f"La línea {c.linea_id} no pertenece al reporte vigente")
        if linea.tipo not in ("detalle", "informativa") or c.linea_id in reglas:
            raise EdicionInvalida(
                f"«{linea.descripcion}» es un total o una línea calculada: no se edita"
            )
        if c.periodo not in por_periodo:
            raise EdicionInvalida(f"El mes {c.periodo} no es del año fiscal {ano_fiscal}")
        if not c.importe.is_finite() or abs(c.importe) > IMPORTE_MAXIMO:
            raise EdicionInvalida(f"Importe no válido en «{linea.descripcion}» ({c.periodo})")
        if previo.get((c.linea_id, c.periodo)) != c.importe:
            hubo_cambio = True
        por_periodo[c.periodo][linea.fila_origen] = ValoresMes(linea.fila_origen, budget=c.importe)
    if not hubo_cambio:
        raise EdicionInvalida("Los importes son iguales a los de la versión actual")

    por_periodo = {p: filas for p, filas in por_periodo.items() if filas}
    sha, tamano = _hash_contenido(por_periodo)
    return importar_budget_mensual(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        version_estructura=estructura,
        por_periodo=por_periodo,
        archivo=DatosArchivo(nombre=NOMBRE_EDICION, sha256=sha, tamano_bytes=tamano),
        ano_fiscal=ano_fiscal,
        mes_inicio=mes_inicio,
        confirmar_reemplazo=True,
        accion_creado="budget.editado",
    )


__all__ = [
    "BaseDesactualizada",
    "CambioBudget",
    "EdicionInvalida",
    "LineaEdicion",
    "VistaEdicion",
    "crear_version_desde_cambios",
    "periodos_de_ano_fiscal",
    "vista_edicion",
]
