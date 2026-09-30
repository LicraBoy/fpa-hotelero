"""Orquesta la carga de un archivo: idempotencia, reemplazo con confirmación y auditoría.

Reglas (ADR 0003):
- El mismo archivo (mismo SHA-256) para los mismos periodos no cambia nada -> `DUPLICADA`.
- Un periodo que ya tiene una carga vigente de OTRO archivo pide confirmación
  (`REQUIERE_CONFIRMACION`, sin escribir nada). Al confirmar, la carga anterior pasa a
  `reemplazada` (se conserva el historial) y se audita.
- Una lectura inválida se rechaza (`RECHAZADA`) y queda registrada en la auditoría.
- Todo lo que escribe va en un SAVEPOINT: o se guarda completo o no se guarda nada.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.contrato import ResultadoLectura
from fpa.modelos.base import ahora_utc
from fpa.modelos.cargas import CargaArchivo, EstadoCarga
from fpa.repositorios.cargas import RepositorioCargas
from fpa.servicios.auditoria import auditar
from fpa.servicios.cargas import DatosArchivo, registrar_carga


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


def _motivos_de_rechazo(resultado: ResultadoLectura) -> list[str]:
    if resultado.fuente is None:
        return ["La lectura no indica su fuente"]
    if not resultado.movimientos:
        return ["El archivo no trae movimientos"]
    if not resultado.es_valido:
        return list(resultado.errores) or ["Débito y Crédito no cuadran"]
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
    controles: dict[str, Any] | None = None,
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

    motivos = _motivos_de_rechazo(resultado)
    if motivos:
        evento("carga.rechazada", None, {**base, "motivos": motivos[:10]})
        return ResultadoCarga(Resolucion.RECHAZADA, motivos=motivos)

    por_periodo = _agrupar(resultado)
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
        return ResultadoCarga(Resolucion.REQUIERE_CONFIRMACION, conflictos=conflictos)

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
        por_periodo_nueva = {c.periodo: c for c in nuevas}
        for vieja in viejas:
            vieja.reemplazada_por_id = por_periodo_nueva[vieja.periodo].id
        db.flush()
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
    )
