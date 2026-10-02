"""Importación del Budget como versión inmutable del plan.

Mismas reglas que las demás importaciones (ADR 0003): el mismo archivo no cambia nada; otro archivo
para el mismo año fiscal pide confirmación y deja la anterior como `reemplazada`; todo en un
SAVEPOINT y con auditoría. Una versión **no se edita nunca**: no existe función que lo permita.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, etiqueta_ano_fiscal, periodos_ytd
from fpa.ingesta.variance_mzt import ValoresMes
from fpa.ingesta.variance_valores import ValoresFila
from fpa.modelos.base import ahora_utc
from fpa.modelos.plan import (
    REEMPLAZADA,
    TIPO_BUDGET,
    VIGENTE,
    LineaPlan,
    LineaPlanMensual,
    ValorCapturado,
    VersionPlan,
)
from fpa.modelos.reporte import VersionEstructuraReporte
from fpa.modelos.tipos import MICRO
from fpa.repositorios.plan import RepositorioPlan
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo


@dataclass
class ResultadoImportacionBudget:
    resolucion: Resolucion
    version: VersionPlan | None = None
    reemplazada: VersionPlan | None = None
    motivos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _micro(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else valor.quantize(MICRO)


def importar_budget(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_estructura: VersionEstructuraReporte,
    valores: dict[int, ValoresFila],
    archivo: DatosArchivo,
    periodo_corte: str,
    ano_fiscal: str,
    confirmar_reemplazo: bool = False,
) -> ResultadoImportacionBudget:
    """Guarda como versión nueva el Budget (mes, YTD y anual) que trae el Excel del Variance.

    El llamador hace `commit` cuando la resolución no sea `REQUIERE_CONFIRMACION`.
    """
    repo = RepositorioPlan(db, hotel_id)
    base: dict[str, Any] = {
        "archivo": archivo.nombre,
        "sha256": archivo.sha256,
        "ano_fiscal": ano_fiscal,
        "periodo_corte": periodo_corte,
    }

    def evento(accion: str, entidad_id: int | None, detalle: dict[str, Any]) -> None:
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion=accion,
            entidad="version_plan",
            entidad_id=entidad_id,
            detalle=detalle,
        )

    if version_estructura.hotel_id != hotel_id:
        raise ValueError("La versión de estructura no pertenece al hotel")
    lineas = {
        x.fila_origen: x for x in RepositorioReporte(db, hotel_id).lineas(version_estructura.id)
    }
    con_budget = {fila: v for fila, v in valores.items() if v.tiene_budget}
    faltantes = sorted(fila for fila in con_budget if fila not in lineas)
    # Unas pocas filas sueltas sin nombre (p. ej. una razón en %) no son líneas del reporte: se
    # ignoran con aviso. Si son más del 5 %, la estructura del archivo no es la vigente.
    if not con_budget or len(faltantes) > max(0, len(con_budget) // 20):
        motivos = (
            ["El archivo no trae Budget (columnas E, J y O)"]
            if not con_budget
            else [
                "La estructura del archivo no coincide con la vigente: filas con Budget sin "
                f"línea ({', '.join(str(f) for f in faltantes[:8])}). Importa primero el reporte."
            ]
        )
        evento("budget.rechazado", None, {**base, "motivos": motivos})
        return ResultadoImportacionBudget(Resolucion.RECHAZADA, motivos=motivos)

    ignoradas = [fila for fila in con_budget if fila in set(faltantes)]
    avisos = (
        [
            f"{len(ignoradas)} filas con cifras y sin línea en la estructura se ignoran: "
            f"{', '.join(str(f) for f in ignoradas[:8])}"
        ]
        if ignoradas
        else []
    )
    con_budget = {fila: v for fila, v in con_budget.items() if fila in lineas}

    vigente = repo.vigente(TIPO_BUDGET, ano_fiscal)
    if vigente is not None and vigente.sha256 == archivo.sha256:
        evento("budget.duplicado", vigente.id, base)
        return ResultadoImportacionBudget(Resolucion.DUPLICADA, version=vigente)
    if vigente is not None and not confirmar_reemplazo:
        return ResultadoImportacionBudget(
            Resolucion.REQUIERE_CONFIRMACION,
            reemplazada=vigente,
            motivos=[
                f"Ya hay un Budget vigente para {ano_fiscal} (versión {vigente.numero}, "
                f"{vigente.nombre_archivo}); confirma para reemplazarlo"
            ],
        )

    with db.begin_nested():
        if vigente is not None:
            vigente.estado = REEMPLAZADA
            vigente.reemplazada_en = ahora_utc()
            db.flush()  # libera el índice de "una vigente por año fiscal" antes de insertar
        version = VersionPlan(
            hotel_id=hotel_id,
            tipo=TIPO_BUDGET,
            numero=repo.siguiente_numero(TIPO_BUDGET),
            ano_fiscal=ano_fiscal,
            periodo_corte=periodo_corte,
            version_estructura_id=version_estructura.id,
            nombre_archivo=archivo.nombre,
            sha256=archivo.sha256,
            estado=VIGENTE,
            n_lineas=len(con_budget),
            usuario_id=usuario_id,
        )
        db.add(version)
        db.flush()
        for fila, v in sorted(con_budget.items()):
            db.add(
                LineaPlan(
                    version_plan_id=version.id,
                    hotel_id=hotel_id,
                    linea_id=lineas[fila].id,
                    mes=_micro(v.mes_budget),
                    ytd=_micro(v.ytd_budget),
                    anual=_micro(v.anual_budget),
                )
            )
        db.flush()
        evento(
            "budget.creado",
            version.id,
            {**base, "numero": version.numero, "n_lineas": version.n_lineas},
        )
        if vigente is not None:
            evento(
                "budget.reemplazado",
                vigente.id,
                {**base, "reemplazado_por_id": version.id, "numero_anterior": vigente.numero},
            )
    return ResultadoImportacionBudget(
        Resolucion.REEMPLAZADA if vigente is not None else Resolucion.CREADA,
        version=version,
        reemplazada=vigente,
        avisos=avisos,
    )


def importar_budget_mensual(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_estructura: VersionEstructuraReporte,
    por_periodo: dict[str, dict[int, ValoresMes]],
    archivo: DatosArchivo,
    ano_fiscal: str,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
    filas_con_cuentas: set[int] | None = None,
    confirmar_reemplazo: bool = False,
) -> ResultadoImportacionBudget:
    """Guarda el Budget **mes a mes** (formato de Mazatlán) como una versión nueva e inmutable.

    Cada mes queda en `LineaPlanMensual`; el acumulado se calcula al consultar. Las líneas
    informativas con Actual (el tipo de cambio) y las de detalle **sin cuentas** se guardan como
    `ValorCapturado` del mes, porque su Actual no sale de los movimientos (`filas_con_cuentas` dice
    qué filas sí tienen cuentas; si es `None`, solo se capturan las informativas). Además se llena
    `LineaPlan` (mes y acumulado del último mes) para el detalle de la versión.
    """
    repo = RepositorioPlan(db, hotel_id)
    periodos = sorted(por_periodo)
    corte = periodos[-1] if periodos else ""
    base: dict[str, Any] = {
        "archivo": archivo.nombre,
        "sha256": archivo.sha256,
        "ano_fiscal": ano_fiscal,
        "periodo_corte": corte,
        "periodos": periodos,
    }

    def evento(accion: str, entidad_id: int | None, detalle: dict[str, Any]) -> None:
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion=accion,
            entidad="version_plan",
            entidad_id=entidad_id,
            detalle=detalle,
        )

    if version_estructura.hotel_id != hotel_id:
        raise ValueError("La versión de estructura no pertenece al hotel")
    lineas = {
        x.fila_origen: x for x in RepositorioReporte(db, hotel_id).lineas(version_estructura.id)
    }
    motivos: list[str] = []
    if not periodos:
        motivos.append("El archivo no trae meses con Budget")
    fuera = [p for p in periodos if etiqueta_ano_fiscal(p, mes_inicio) != ano_fiscal]
    if fuera:
        motivos.append(
            f"Los meses {', '.join(fuera)} no pertenecen al año fiscal {ano_fiscal}: revisa el "
            "año fiscal indicado"
        )
    filas_con_budget = {
        fila for datos in por_periodo.values() for fila, v in datos.items() if v.budget is not None
    }
    faltantes = sorted(fila for fila in filas_con_budget if fila not in lineas)
    if periodos and (not filas_con_budget or len(faltantes) > max(0, len(filas_con_budget) // 20)):
        motivos.append(
            "El archivo no trae Budget"
            if not filas_con_budget
            else "La estructura del archivo no coincide con la vigente: filas con Budget sin "
            f"línea ({', '.join(str(f) for f in faltantes[:8])}). Importa primero el reporte."
        )
    if motivos:
        evento("budget.rechazado", None, {**base, "motivos": motivos})
        return ResultadoImportacionBudget(Resolucion.RECHAZADA, motivos=motivos)

    avisos = (
        [
            f"{len(faltantes)} filas con cifras y sin línea en la estructura se ignoran: "
            f"{', '.join(str(f) for f in faltantes[:8])}"
        ]
        if faltantes
        else []
    )
    vigente = repo.vigente(TIPO_BUDGET, ano_fiscal)
    if vigente is not None and vigente.sha256 == archivo.sha256:
        evento("budget.duplicado", vigente.id, base)
        return ResultadoImportacionBudget(Resolucion.DUPLICADA, version=vigente)
    if vigente is not None and not confirmar_reemplazo:
        return ResultadoImportacionBudget(
            Resolucion.REQUIERE_CONFIRMACION,
            reemplazada=vigente,
            motivos=[
                f"Ya hay un Budget vigente para {ano_fiscal} (versión {vigente.numero}, "
                f"{vigente.nombre_archivo}); confirma para reemplazarlo"
            ],
        )

    with db.begin_nested():
        if vigente is not None:
            vigente.estado = REEMPLAZADA
            vigente.reemplazada_en = ahora_utc()
            db.flush()
        version = VersionPlan(
            hotel_id=hotel_id,
            tipo=TIPO_BUDGET,
            numero=repo.siguiente_numero(TIPO_BUDGET),
            ano_fiscal=ano_fiscal,
            periodo_corte=corte,
            version_estructura_id=version_estructura.id,
            nombre_archivo=archivo.nombre,
            sha256=archivo.sha256,
            estado=VIGENTE,
            n_lineas=len(filas_con_budget & set(lineas)),
            usuario_id=usuario_id,
        )
        db.add(version)
        db.flush()
        acumulado: dict[int, Decimal] = {}
        ytd = periodos_ytd(corte, mes_inicio)
        completo = all(p in por_periodo for p in ytd)
        for periodo in periodos:
            for fila, v in sorted(por_periodo[periodo].items()):
                linea = lineas.get(fila)
                if linea is None:
                    continue
                importe = _micro(v.budget)
                if importe is not None:
                    db.add(
                        LineaPlanMensual(
                            version_plan_id=version.id,
                            hotel_id=hotel_id,
                            linea_id=linea.id,
                            periodo=periodo,
                            importe=importe,
                        )
                    )
                    if periodo in ytd and linea.tipo != "informativa":
                        acumulado[linea.id] = acumulado.get(linea.id, Decimal(0)) + importe
                sin_cuentas = (
                    linea.tipo == "detalle"
                    and filas_con_cuentas is not None
                    and fila not in filas_con_cuentas
                )
                if (linea.tipo == "informativa" or sin_cuentas) and v.actual is not None:
                    _guardar_capturado(db, hotel_id, version_estructura.id, linea.id, periodo, v)
        for fila in sorted(filas_con_budget & set(lineas)):
            linea = lineas[fila]
            del_corte = por_periodo[corte].get(fila)
            db.add(
                LineaPlan(
                    version_plan_id=version.id,
                    hotel_id=hotel_id,
                    linea_id=linea.id,
                    mes=_micro(del_corte.budget) if del_corte else None,
                    ytd=_micro(acumulado.get(linea.id)) if completo else None,
                    anual=None,
                )
            )
        db.flush()
        evento(
            "budget.creado",
            version.id,
            {**base, "numero": version.numero, "n_lineas": version.n_lineas},
        )
        if vigente is not None:
            evento(
                "budget.reemplazado",
                vigente.id,
                {**base, "reemplazado_por_id": version.id, "numero_anterior": vigente.numero},
            )
    return ResultadoImportacionBudget(
        Resolucion.REEMPLAZADA if vigente is not None else Resolucion.CREADA,
        version=version,
        reemplazada=vigente,
        avisos=avisos,
    )


def _guardar_capturado(
    db: Session,
    hotel_id: int,
    version_estructura_id: int,
    linea_id: int,
    periodo: str,
    v: ValoresMes,
) -> None:
    """Guarda el Actual capturado de una línea informativa; uno capturado a mano se respeta."""
    importe = _micro(v.actual)
    if importe is None:
        return
    existente = db.scalar(
        select(ValorCapturado).where(
            ValorCapturado.hotel_id == hotel_id,
            ValorCapturado.version_estructura_id == version_estructura_id,
            ValorCapturado.linea_id == linea_id,
            ValorCapturado.periodo == periodo,
        )
    )
    if existente is None:
        db.add(
            ValorCapturado(
                hotel_id=hotel_id,
                version_estructura_id=version_estructura_id,
                linea_id=linea_id,
                periodo=periodo,
                importe=importe,
                origen="excel",
            )
        )
    elif existente.origen == "excel":
        existente.importe = importe
