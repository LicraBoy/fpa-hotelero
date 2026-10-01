"""Importación del Budget como versión inmutable del plan.

Mismas reglas que las demás importaciones (ADR 0003): el mismo archivo no cambia nada; otro archivo
para el mismo año fiscal pide confirmación y deja la anterior como `reemplazada`; todo en un
SAVEPOINT y con auditoría. Una versión **no se edita nunca**: no existe función que lo permita.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from fpa.ingesta.variance_valores import ValoresFila
from fpa.modelos.base import ahora_utc
from fpa.modelos.plan import REEMPLAZADA, TIPO_BUDGET, VIGENTE, LineaPlan, VersionPlan
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
