"""Versionado del mapeo: editar solo borradores, copiar, aprobar y dejar historial.

Ciclo: `borrador` (editable) -> `aprobada` (inmutable, una vigente por hotel) -> `reemplazada`.
Cualquier cambio a una versión aprobada se hace en un **borrador nuevo** copiado de ella. Toda
acción queda en la bitácora de auditoría.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fpa.modelos.base import ahora_utc
from fpa.modelos.mapeo import (
    APROBADA,
    BORRADOR,
    REEMPLAZADA,
    CuentaExcluidaMapeo,
    MapeoLineaCuenta,
    VersionMapeo,
)
from fpa.modelos.saldos import SaldoMensualCuenta
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.validacion_mapeo import ReporteMapeo, validar_mapeo


class VersionInmutable(Exception):
    """Se intentó cambiar una versión que ya no es un borrador."""


class MapeoInvalido(ValueError):
    """El cambio pedido no es válido (línea, cuenta, signo o duplicado)."""


class AprobacionBloqueada(Exception):
    """El borrador no se puede aprobar; `motivos` explica por qué."""

    def __init__(self, motivos: list[str], reportes: list[ReporteMapeo] | None = None) -> None:
        super().__init__("; ".join(motivos))
        self.motivos = motivos
        self.reportes = reportes or []


class _Contexto:
    """Datos comunes de una operación para no repetirlos en cada llamada a la bitácora."""

    def __init__(self, db: Session, organizacion_id: int, hotel_id: int, usuario_id: int | None):
        self.db = db
        self.organizacion_id = organizacion_id
        self.hotel_id = hotel_id
        self.usuario_id = usuario_id
        self.repo = RepositorioMapeo(db, hotel_id)

    def auditar(self, accion: str, version_id: int | None, detalle: dict[str, Any]) -> None:
        auditar(
            self.db,
            organizacion_id=self.organizacion_id,
            hotel_id=self.hotel_id,
            usuario_id=self.usuario_id,
            accion=accion,
            entidad="version_mapeo",
            entidad_id=version_id,
            detalle=detalle,
        )

    def borrador_editable(self, version_id: int) -> VersionMapeo:
        version = self.repo.obtener(version_id)
        if version is None:
            raise LookupError("Versión de mapeo no encontrada")
        if version.estado != BORRADOR:
            raise VersionInmutable(
                f"La versión {version.numero} está {version.estado}: solo se edita un borrador"
            )
        return version


def crear_borrador_desde(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_origen_id: int | None = None,
) -> VersionMapeo:
    """Copia una versión (por omisión la aprobada vigente) en un borrador nuevo."""
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    if ctx.repo.borrador() is not None:
        raise MapeoInvalido("Ya hay un borrador abierto; apruébalo o descártalo antes")
    origen = ctx.repo.obtener(version_origen_id) if version_origen_id else ctx.repo.aprobada()
    if origen is None:
        raise LookupError("No hay una versión de mapeo de la cual copiar")
    with db.begin_nested():
        nueva = VersionMapeo(
            hotel_id=hotel_id,
            numero=ctx.repo.siguiente_numero(),
            version_estructura_id=origen.version_estructura_id,
            origen=f"copia de la versión {origen.numero}",
            creada_por_id=usuario_id,
        )
        db.add(nueva)
        db.flush()
        for v in ctx.repo.vinculos(origen.id):
            db.add(
                MapeoLineaCuenta(
                    version_mapeo_id=nueva.id,
                    hotel_id=hotel_id,
                    linea_id=v.linea_id,
                    cuenta_codigo=v.cuenta_codigo,
                    signo=v.signo,
                    origen=v.origen,
                )
            )
        for e in ctx.repo.excluidas(origen.id):
            db.add(
                CuentaExcluidaMapeo(
                    version_mapeo_id=nueva.id,
                    hotel_id=hotel_id,
                    cuenta_codigo=e.cuenta_codigo,
                    motivo=e.motivo,
                    usuario_id=e.usuario_id,
                )
            )
        db.flush()
        ctx.auditar(
            "mapeo.borrador_creado",
            nueva.id,
            {"numero": nueva.numero, "copia_de": origen.id, "version_origen": origen.numero},
        )
    return nueva


def agregar_vinculo(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_id: int,
    linea_id: int,
    cuenta_codigo: str,
    signo: int,
) -> MapeoLineaCuenta:
    """Agrega un vínculo cuenta -> línea de detalle, o cambia su signo si ya existe."""
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    version = ctx.borrador_editable(version_id)
    if signo not in (1, -1):
        raise MapeoInvalido("El signo debe ser +1 o -1")
    codigo = cuenta_codigo.strip()
    if not codigo:
        raise MapeoInvalido("Falta el código de cuenta")
    linea = next(
        (
            x
            for x in RepositorioReporte(db, hotel_id).lineas(version.version_estructura_id)
            if x.id == linea_id
        ),
        None,
    )
    if linea is None:
        raise MapeoInvalido("La línea no existe en la estructura de esta versión")
    if linea.tipo != "detalle":
        raise MapeoInvalido("Solo las líneas de detalle reciben cuentas")
    existente = db.scalar(
        select(MapeoLineaCuenta).where(
            MapeoLineaCuenta.version_mapeo_id == version.id,
            MapeoLineaCuenta.hotel_id == hotel_id,
            MapeoLineaCuenta.linea_id == linea_id,
            MapeoLineaCuenta.cuenta_codigo == codigo,
        )
    )
    anterior = existente.signo if existente is not None else None
    if existente is None:
        existente = MapeoLineaCuenta(
            version_mapeo_id=version.id,
            hotel_id=hotel_id,
            linea_id=linea_id,
            cuenta_codigo=codigo,
            signo=signo,
            origen="manual",
        )
        db.add(existente)
    else:
        existente.signo = signo
        existente.origen = "manual"
    # Una cuenta que ahora tiene línea deja de estar excluida
    db.execute(
        delete(CuentaExcluidaMapeo).where(
            CuentaExcluidaMapeo.version_mapeo_id == version.id,
            CuentaExcluidaMapeo.hotel_id == hotel_id,
            CuentaExcluidaMapeo.cuenta_codigo == codigo,
        )
    )
    db.flush()
    ctx.auditar(
        "mapeo.editado",
        version.id,
        {
            "cambio": "vinculo_agregado" if anterior is None else "signo_cambiado",
            "linea_id": linea_id,
            "cuenta": codigo,
            "signo": signo,
            "signo_anterior": anterior,
        },
    )
    return existente


def quitar_vinculo(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_id: int,
    linea_id: int,
    cuenta_codigo: str,
) -> None:
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    version = ctx.borrador_editable(version_id)
    vinculo = db.scalar(
        select(MapeoLineaCuenta).where(
            MapeoLineaCuenta.version_mapeo_id == version.id,
            MapeoLineaCuenta.hotel_id == hotel_id,
            MapeoLineaCuenta.linea_id == linea_id,
            MapeoLineaCuenta.cuenta_codigo == cuenta_codigo,
        )
    )
    if vinculo is None:
        raise LookupError("El vínculo no existe en esta versión")
    db.delete(vinculo)
    db.flush()
    ctx.auditar(
        "mapeo.editado",
        version.id,
        {"cambio": "vinculo_quitado", "linea_id": linea_id, "cuenta": cuenta_codigo},
    )


def excluir_cuenta(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_id: int,
    cuenta_codigo: str,
    motivo: str,
) -> CuentaExcluidaMapeo:
    """Registra que una cuenta con movimientos se deja fuera del reporte a propósito."""
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    version = ctx.borrador_editable(version_id)
    codigo, razon = cuenta_codigo.strip(), motivo.strip()
    if not codigo or not razon:
        raise MapeoInvalido("Hay que indicar la cuenta y el motivo de la exclusión")
    existente = db.scalar(
        select(CuentaExcluidaMapeo).where(
            CuentaExcluidaMapeo.version_mapeo_id == version.id,
            CuentaExcluidaMapeo.hotel_id == hotel_id,
            CuentaExcluidaMapeo.cuenta_codigo == codigo,
        )
    )
    if existente is None:
        existente = CuentaExcluidaMapeo(
            version_mapeo_id=version.id,
            hotel_id=hotel_id,
            cuenta_codigo=codigo,
            motivo=razon,
            usuario_id=usuario_id,
        )
        db.add(existente)
    else:
        existente.motivo = razon
        existente.usuario_id = usuario_id
    db.flush()
    ctx.auditar(
        "mapeo.editado",
        version.id,
        {"cambio": "cuenta_excluida", "cuenta": codigo, "motivo": razon},
    )
    return existente


def quitar_exclusion(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_id: int,
    cuenta_codigo: str,
) -> None:
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    version = ctx.borrador_editable(version_id)
    existente = db.scalar(
        select(CuentaExcluidaMapeo).where(
            CuentaExcluidaMapeo.version_mapeo_id == version.id,
            CuentaExcluidaMapeo.hotel_id == hotel_id,
            CuentaExcluidaMapeo.cuenta_codigo == cuenta_codigo,
        )
    )
    if existente is None:
        raise LookupError("La cuenta no está excluida en esta versión")
    db.delete(existente)
    db.flush()
    ctx.auditar(
        "mapeo.editado", version.id, {"cambio": "exclusion_quitada", "cuenta": cuenta_codigo}
    )


def periodos_con_movimientos(db: Session, hotel_id: int) -> list[str]:
    return sorted(
        db.scalars(
            select(SaldoMensualCuenta.periodo)
            .where(SaldoMensualCuenta.hotel_id == hotel_id)
            .distinct()
        )
    )


def aprobar(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_id: int,
    periodos: Collection[str] | None = None,
    notas: str | None = None,
) -> VersionMapeo:
    """Aprueba un borrador si no deja cuentas con movimiento sin mapear.

    Se valida contra `periodos` (por omisión todos los que tienen movimientos cargados). La
    aprobada anterior pasa a `reemplazada`. Una versión aprobada ya no se puede editar.
    """
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    version = ctx.borrador_editable(version_id)
    lista = sorted(periodos) if periodos else periodos_con_movimientos(db, hotel_id)
    if not lista:
        raise AprobacionBloqueada(
            ["No hay movimientos cargados contra los cuales validar el mapeo"]
        )
    reportes = [
        validar_mapeo(db, hotel_id=hotel_id, version_mapeo_id=version.id, periodo=p) for p in lista
    ]
    motivos = [m for r in reportes for m in r.bloqueantes]
    if motivos:
        raise AprobacionBloqueada(motivos, reportes)
    with db.begin_nested():
        anterior = ctx.repo.aprobada()
        ahora = ahora_utc()
        if anterior is not None:
            anterior.estado = REEMPLAZADA
            anterior.cerrada_en = ahora
            db.flush()  # libera el índice de "una aprobada por hotel" antes de aprobar la nueva
        version.estado = APROBADA
        version.aprobada_por_id = usuario_id
        version.aprobada_en = ahora
        if notas:
            version.notas = notas
        db.flush()
        ctx.auditar(
            "mapeo.aprobado",
            version.id,
            {
                "numero": version.numero,
                "periodos_validados": lista,
                "reemplaza": anterior.numero if anterior else None,
                "excluidas": sorted(e.cuenta_codigo for e in ctx.repo.excluidas(version.id)),
            },
        )
    return version


def descartar_borrador(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_id: int,
) -> None:
    ctx = _Contexto(db, organizacion_id, hotel_id, usuario_id)
    version = ctx.borrador_editable(version_id)
    version.estado = "descartada"
    version.cerrada_en = ahora_utc()
    db.flush()
    ctx.auditar("mapeo.borrador_descartado", version.id, {"numero": version.numero})
