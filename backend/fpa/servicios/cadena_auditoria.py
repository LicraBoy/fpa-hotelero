"""Cadena de hashes de la bitácora (Arquitectura §8.8, Fase 5.5).

Cada evento guarda el SHA-256 de su contenido junto con el hash del evento anterior **de la misma
organización**. Alterar un campo, borrar un evento del medio o intercalar uno cambia los hashes de
ahí en adelante, y `verificar` lo detecta. Lo que no puede detectar solo con la base es que se
borren los **últimos** eventos: por eso `verificar` devuelve el último hash, para anotarlo aparte
(p. ej. en el acta de cada cierre).

El contenido que se firma es canónico: campos fijos, fecha en UTC con microsegundos y el detalle en
JSON con llaves ordenadas. El `id` no se firma (lo asigna la base).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.auditoria import EventoAuditoria

GENESIS = "0" * 64


def _marca(momento: datetime) -> str:
    if momento.tzinfo is not None:
        momento = momento.astimezone(UTC).replace(tzinfo=None)
    return momento.isoformat(timespec="microseconds")


def calcular_hash(
    *,
    hash_previo: str,
    organizacion_id: int,
    hotel_id: int | None,
    usuario_id: int | None,
    accion: str,
    entidad: str,
    entidad_id: int | None,
    detalle: dict[str, Any] | None,
    creado_en: datetime,
) -> str:
    contenido = json.dumps(
        [
            hash_previo,
            organizacion_id,
            hotel_id,
            usuario_id,
            accion,
            entidad,
            entidad_id,
            detalle,
            _marca(creado_en),
        ],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def hash_de(evento: EventoAuditoria, hash_previo: str) -> str:
    return calcular_hash(
        hash_previo=hash_previo,
        organizacion_id=evento.organizacion_id,
        hotel_id=evento.hotel_id,
        usuario_id=evento.usuario_id,
        accion=evento.accion,
        entidad=evento.entidad,
        entidad_id=evento.entidad_id,
        detalle=evento.detalle,
        creado_en=evento.creado_en,
    )


def ultimo_hash(db: Session, organizacion_id: int) -> str:
    """Hash del último evento de la organización (o el génesis si todavía no hay ninguno)."""
    return (
        db.scalar(
            select(EventoAuditoria.hash)
            .where(EventoAuditoria.organizacion_id == organizacion_id)
            .order_by(EventoAuditoria.id.desc())
            .limit(1)
        )
        or GENESIS
    )


@dataclass(frozen=True)
class ResultadoVerificacion:
    integra: bool
    eventos: int
    ultimo_hash: str
    primer_alterado_id: int | None = None
    motivo: str | None = None


def verificar(db: Session, organizacion_id: int) -> ResultadoVerificacion:
    """Recorre toda la cadena de la organización y dice si algo cambió."""
    previo = GENESIS
    n = 0
    for e in db.scalars(
        select(EventoAuditoria)
        .where(EventoAuditoria.organizacion_id == organizacion_id)
        .order_by(EventoAuditoria.id)
    ):
        n += 1
        if e.hash_previo != previo:
            return ResultadoVerificacion(
                False, n, previo, e.id, "Falta un evento o se intercaló otro antes de este"
            )
        if e.hash != hash_de(e, previo):
            return ResultadoVerificacion(
                False, n, previo, e.id, "El contenido de este evento cambió"
            )
        previo = e.hash
    return ResultadoVerificacion(True, n, previo)
