"""Flujo de cierre de un periodo del Variance (Fase 5.4).

    Borrador → Comentado → Revisado → Aprobado → Bloqueado

- «Devolver» regresa de Comentado o Revisado a Borrador; «Reabrir» regresa de Aprobado a Borrador
  (solo quien aprueba). Ambas piden una nota. Un periodo Bloqueado ya no se reabre.
- Al **aprobar** se congelan las versiones que produjeron las cifras y una huella de las cifras.
- Mientras esté Aprobado o Bloqueado: el Variance del periodo se calcula con las versiones
  congeladas (aunque después se apruebe otro mapeo) y no se aceptan recargas ni capturas en los
  meses de su acumulado.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.identidad.permisos import Permiso
from fpa.modelos.base import ahora_utc
from fpa.modelos.cierre import ESTADOS_CERRADOS, CierrePeriodo, CierreTransicion
from fpa.repositorios.cargas import RepositorioCargas
from fpa.servicios.auditoria import auditar
from fpa.servicios.cierre_candado import PeriodoCerrado, exigir_abierto, periodos_cerrados
from fpa.servicios.variance import ReporteVariance, calcular_variance


@dataclass(frozen=True)
class Transicion:
    desde: str
    hacia: str
    permiso: Permiso
    etiqueta: str
    pide_nota: bool = False


TRANSICIONES: tuple[Transicion, ...] = (
    Transicion("borrador", "comentado", Permiso.CIERRE_REVISAR, "Marcar como comentado"),
    Transicion("comentado", "revisado", Permiso.CIERRE_REVISAR, "Marcar como revisado"),
    Transicion("comentado", "borrador", Permiso.CIERRE_REVISAR, "Devolver a borrador", True),
    Transicion("revisado", "borrador", Permiso.CIERRE_REVISAR, "Devolver a borrador", True),
    Transicion("revisado", "aprobado", Permiso.CIERRE_APROBAR, "Aprobar"),
    Transicion("aprobado", "bloqueado", Permiso.CIERRE_BLOQUEAR, "Bloquear"),
    Transicion("aprobado", "borrador", Permiso.CIERRE_APROBAR, "Reabrir", True),
)


class CierreInvalido(Exception):
    """Transición no permitida o datos que la impiden. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


def transicion_de(desde: str, hacia: str) -> Transicion | None:
    return next((t for t in TRANSICIONES if t.desde == desde and t.hacia == hacia), None)


def cierre_de(db: Session, hotel_id: int, periodo: str) -> CierrePeriodo | None:
    return db.scalar(
        select(CierrePeriodo).where(
            CierrePeriodo.hotel_id == hotel_id, CierrePeriodo.periodo == periodo
        )
    )


def estado_de(db: Session, hotel_id: int, periodo: str) -> str:
    cierre = cierre_de(db, hotel_id, periodo)
    return cierre.estado if cierre else "borrador"


def historial(db: Session, cierre: CierrePeriodo | None) -> list[CierreTransicion]:
    if cierre is None:
        return []
    return list(
        db.scalars(
            select(CierreTransicion)
            .where(CierreTransicion.cierre_id == cierre.id)
            .order_by(CierreTransicion.id)
        )
    )


def versiones_congeladas(db: Session, hotel_id: int, periodo: str) -> tuple[int, int | None] | None:
    """`(mapeo, budget)` con que se aprobó el periodo, si hoy está Aprobado o Bloqueado."""
    cierre = cierre_de(db, hotel_id, periodo)
    if cierre is None or cierre.estado not in ESTADOS_CERRADOS or cierre.version_mapeo_id is None:
        return None
    return cierre.version_mapeo_id, cierre.version_plan_id


def huella_de(r: ReporteVariance) -> str:
    """SHA-256 de las cifras del reporte: prueba de que no cambiaron desde la aprobación."""
    filas = [
        [
            linea.id,
            *(
                str(c.actual) + "|" + str(c.budget) + "|" + str(c.var) + "|" + str(c.pct)
                for c in (
                    r.resultado[linea.id].mes,
                    r.resultado[linea.id].ytd,
                    r.resultado[linea.id].anual,
                )
            ),
        ]
        for linea in r.lineas
    ]
    return hashlib.sha256(json.dumps(filas, sort_keys=True).encode()).hexdigest()


def _congelar(db: Session, cierre: CierrePeriodo) -> None:
    """Fija versiones y cifras con las que está hoy el periodo (al aprobarlo)."""
    try:
        r = calcular_variance(db, hotel_id=cierre.hotel_id, periodo=cierre.periodo)
    except LookupError as e:
        raise CierreInvalido(409, str(e.args[0]) if e.args else "Falta el mapeo aprobado") from None
    repo = RepositorioCargas(db, cierre.hotel_id)
    cargas = []
    for mes in r.periodos_ytd:
        carga = repo.vigente_de_periodo(mes)
        cargas.append(
            {
                "periodo": mes,
                "carga_id": carga.id if carga else None,
                "sha256": carga.sha256 if carga else None,
                "archivo": carga.nombre_archivo if carga else None,
            }
        )
    from fpa.repositorios.mapeo import RepositorioMapeo

    mapeo = RepositorioMapeo(db, cierre.hotel_id).obtener(r.version_mapeo_id)
    cierre.version_mapeo_id = r.version_mapeo_id
    cierre.version_plan_id = r.version_plan_id
    cierre.version_estructura_id = mapeo.version_estructura_id if mapeo else None
    cierre.congelado = {
        "ano_fiscal": r.ano_fiscal,
        "periodos_ytd": r.periodos_ytd,
        "periodos_sin_datos": r.periodos_sin_datos,
        "cargas": cargas,
    }
    cierre.huella_cifras = huella_de(r)


def transicionar(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int,
    puede: dict[Permiso, bool] | None,
    periodo: str,
    hacia: str,
    nota: str | None,
) -> CierrePeriodo:
    """Aplica una transición. `CierreInvalido` si no existe, falta permiso, nota o datos."""
    cierre = cierre_de(db, hotel_id, periodo)
    desde = cierre.estado if cierre else "borrador"
    t = transicion_de(desde, hacia)
    if t is None:
        raise CierreInvalido(409, f"No se puede pasar de «{desde}» a «{hacia}»")
    if puede is not None and not puede.get(t.permiso, False):
        raise CierreInvalido(403, "Tu rol no puede hacer este cambio de estado")
    nota = (nota or "").strip() or None
    if t.pide_nota and nota is None:
        raise CierreInvalido(422, "Escribe el motivo: es obligatorio para este cambio")
    if nota is not None and len(nota) > 1000:
        raise CierreInvalido(422, "La nota admite hasta 1000 caracteres")
    ahora = ahora_utc()
    if cierre is None:
        cierre = CierrePeriodo(
            hotel_id=hotel_id,
            periodo=periodo,
            estado="borrador",
            creado_en=ahora,
            actualizado_en=ahora,
        )
        db.add(cierre)
        db.flush()
    if hacia == "aprobado":
        _congelar(db, cierre)
    cierre.estado = hacia
    cierre.actualizado_en = ahora
    db.add(
        CierreTransicion(
            cierre_id=cierre.id,
            desde=desde,
            hacia=hacia,
            usuario_id=usuario_id,
            nota=nota,
            creado_en=ahora,
        )
    )
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion=f"cierre.{hacia}",
        entidad="cierre_periodo",
        entidad_id=cierre.id,
        detalle={
            "periodo": periodo,
            "desde": desde,
            "hacia": hacia,
            "nota": nota,
            **(
                {
                    "version_mapeo_id": cierre.version_mapeo_id,
                    "version_plan_id": cierre.version_plan_id,
                    "huella": cierre.huella_cifras,
                }
                if hacia == "aprobado"
                else {}
            ),
        },
    )
    return cierre


__all__ = ["PeriodoCerrado", "exigir_abierto", "periodos_cerrados"]
