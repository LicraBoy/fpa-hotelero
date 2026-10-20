"""Orquesta la carga de un archivo: idempotencia, reemplazo con confirmación y auditoría.

Reglas (ADR 0003):
- El mismo archivo (mismo SHA-256) para los mismos periodos no cambia nada -> `DUPLICADA`.
- Un periodo que ya tiene una carga vigente de OTRO archivo pide confirmación
  (`REQUIERE_CONFIRMACION`, sin escribir nada). Al confirmar, la carga anterior pasa a
  `reemplazada` (se conserva el historial) y se audita.
- Una lectura inválida se rechaza (`RECHAZADA`) y queda registrada en la auditoría.
- Todo lo que escribe va en un SAVEPOINT: o se guarda completo o no se guarda nada.
"""

from collections.abc import Collection
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from fpa.calidad.evaluacion import ReporteCalidad, evaluar
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.contrato import ResultadoLectura
from fpa.modelos.base import ahora_utc
from fpa.modelos.cargas import CargaArchivo, EstadoCarga
from fpa.repositorios.cargas import RepositorioCargas
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.servicios.auditoria import auditar
from fpa.servicios.cargas import DatosArchivo, registrar_carga
from fpa.servicios.catalogo import actualizar_catalogo
from fpa.servicios.cierre_candado import PeriodoCerrado, exigir_abierto
from fpa.servicios.saldos import recalcular_saldos


class Resolucion(StrEnum):
    CREADA = "creada"
    DUPLICADA = "duplicada"
    REQUIERE_CONFIRMACION = "requiere_confirmacion"
    REEMPLAZADA = "reemplazada"
    RECHAZADA = "rechazada"


@dataclass(frozen=True)
class Conflicto:
    """Un periodo que ya tiene una carga vigente distinta de la que se quiere guardar."""

    periodo: str
    carga_vigente_id: int
    archivo_vigente: str
    n_vigente: int
    debito_vigente: Decimal
    credito_vigente: Decimal
    n_nuevo: int
    debito_nuevo: Decimal
    credito_nuevo: Decimal


@dataclass
class ResultadoCarga:
    resolucion: Resolucion
    cargas: list[CargaArchivo] = field(default_factory=list)
    reemplazadas: list[CargaArchivo] = field(default_factory=list)
    conflictos: list[Conflicto] = field(default_factory=list)
    sin_cambio: list[str] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)
    reporte: ReporteCalidad | None = None


def _motivos_basicos(resultado: ResultadoLectura) -> list[str]:
    if resultado.fuente is None:
        return ["La lectura no indica su fuente"]
    if not resultado.movimientos:
        return ["El archivo no trae movimientos"]
    return []


def _agrupar(resultado: ResultadoLectura) -> dict[str, list[MovimientoLeido]]:
    grupos: dict[str, list[MovimientoLeido]] = {}
    for m in resultado.movimientos:
        grupos.setdefault(m.periodo, []).append(m)
    return grupos


def _total(movs: list[MovimientoLeido], campo: str) -> Decimal:
    return sum((getattr(m, campo) for m in movs), Decimal("0"))


def cargar_archivo(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    resultado: ResultadoLectura,
    archivo: DatosArchivo,
    confirmar_reemplazo: bool = False,
    periodos_esperados: Collection[str] | None = None,
    cuentas_conocidas: Collection[str] | None = None,
) -> ResultadoCarga:
    """No lanza excepciones por condiciones de negocio; devuelve una `Resolucion`.

    El llamador hace `commit` cuando la resolución no sea `REQUIERE_CONFIRMACION`.
    """
    repo = RepositorioCargas(db, hotel_id)

    def evento(accion: str, entidad_id: int | None, detalle: dict[str, Any]) -> None:
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion=accion,
            entidad="carga_archivo",
            entidad_id=entidad_id,
            detalle=detalle,
        )

    base = {"archivo": archivo.nombre, "sha256": archivo.sha256}

    motivos = _motivos_basicos(resultado)
    if motivos:
        evento("carga.rechazada", None, {**base, "motivos": motivos[:10]})
        return ResultadoCarga(Resolucion.RECHAZADA, motivos=motivos)

    if cuentas_conocidas is None:
        cuentas_conocidas = RepositorioCatalogo(db, hotel_id).codigos_con_movimientos()
    catalogo = RepositorioCatalogo(db, hotel_id)
    reporte = evaluar(
        resultado,
        periodos_esperados=periodos_esperados,
        cuentas_conocidas=cuentas_conocidas,
        cuentas_oficiales=catalogo.codigos_oficiales(),
        cuentas_inactivas=catalogo.codigos_inactivos(),
    )
    if not reporte.aprobado:
        motivos = reporte.motivos_de_rechazo()
        evento("carga.rechazada", None, {**base, "motivos": motivos[:10]})
        return ResultadoCarga(Resolucion.RECHAZADA, motivos=motivos, reporte=reporte)
    controles = reporte.a_dict()

    por_periodo = _agrupar(resultado)
    # Un periodo aprobado o bloqueado no acepta recargas (el mismo archivo no cambia nada)
    cambios = [
        mes
        for mes in por_periodo
        if (vigente := repo.vigente_de_periodo(mes)) is None or vigente.sha256 != archivo.sha256
    ]
    try:
        exigir_abierto(db, hotel_id, cambios)
    except PeriodoCerrado as e:
        evento("carga.rechazada", None, {**base, "motivos": [str(e)]})
        return ResultadoCarga(Resolucion.RECHAZADA, motivos=[str(e)])
    nuevos: list[str] = []
    iguales: list[CargaArchivo] = []
    en_conflicto: dict[str, CargaArchivo] = {}
    for periodo in sorted(por_periodo):
        vigente = repo.vigente_de_periodo(periodo)
        if vigente is None:
            nuevos.append(periodo)
        elif vigente.sha256 == archivo.sha256:
            iguales.append(vigente)
        else:
            en_conflicto[periodo] = vigente

    if not nuevos and not en_conflicto:
        evento("carga.duplicada", None, {**base, "periodos": [c.periodo for c in iguales]})
        return ResultadoCarga(
            Resolucion.DUPLICADA, cargas=iguales, sin_cambio=[c.periodo for c in iguales]
        )

    if en_conflicto and not confirmar_reemplazo:
        conflictos = [
            Conflicto(
                periodo=p,
                carga_vigente_id=v.id,
                archivo_vigente=v.nombre_archivo,
                n_vigente=v.n_movimientos,
                debito_vigente=v.total_debito,
                credito_vigente=v.total_credito,
                n_nuevo=len(por_periodo[p]),
                debito_nuevo=_total(por_periodo[p], "debito"),
                credito_nuevo=_total(por_periodo[p], "credito"),
            )
            for p, v in en_conflicto.items()
        ]
        return ResultadoCarga(
            Resolucion.REQUIERE_CONFIRMACION, conflictos=conflictos, reporte=reporte
        )

    a_guardar = {*nuevos, *en_conflicto}
    filtrado = replace(
        resultado, movimientos=[m for m in resultado.movimientos if m.periodo in a_guardar]
    )
    viejas = list(en_conflicto.values())
    with db.begin_nested():
        ahora = ahora_utc()
        for vieja in viejas:
            vieja.estado = EstadoCarga.REEMPLAZADA.value
            vieja.reemplazada_en = ahora
        db.flush()  # libera el índice de "una vigente por periodo" antes de insertar
        nuevas = registrar_carga(
            db,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            resultado=filtrado,
            archivo=archivo,
            controles=controles,
        )
        actualizar_catalogo(
            db, hotel_id=hotel_id, resultado=resultado, movimientos=filtrado.movimientos
        )
        por_periodo_nueva = {c.periodo: c for c in nuevas}
        for vieja in viejas:
            vieja.reemplazada_por_id = por_periodo_nueva[vieja.periodo].id
        db.flush()
        for periodo in sorted(a_guardar):
            recalcular_saldos(db, hotel_id=hotel_id, periodo=periodo)
        for carga in nuevas:
            evento(
                "carga.creada",
                carga.id,
                {
                    **base,
                    "periodo": carga.periodo,
                    "fuente": carga.fuente,
                    "n_movimientos": carga.n_movimientos,
                    "total_debito": str(carga.total_debito),
                    "total_credito": str(carga.total_credito),
                },
            )
        for vieja in viejas:
            nueva = por_periodo_nueva[vieja.periodo]
            evento(
                "carga.reemplazada",
                vieja.id,
                {
                    **base,
                    "periodo": vieja.periodo,
                    "reemplazada_por_id": nueva.id,
                    "archivo_anterior": vieja.nombre_archivo,
                    "sha256_anterior": vieja.sha256,
                    "n_anterior": vieja.n_movimientos,
                    "n_nuevo": nueva.n_movimientos,
                    "total_debito_anterior": str(vieja.total_debito),
                    "total_debito_nuevo": str(nueva.total_debito),
                },
            )
    return ResultadoCarga(
        Resolucion.REEMPLAZADA if viejas else Resolucion.CREADA,
        cargas=nuevas,
        reemplazadas=viejas,
        sin_cambio=[c.periodo for c in iguales],
        reporte=reporte,
    )
