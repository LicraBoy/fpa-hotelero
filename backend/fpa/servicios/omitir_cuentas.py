"""Omitir cuentas del reporte a propósito, como una versión nueva del mapeo.

Una versión aprobada del mapeo **no se edita**: para dejar fuera una cuenta que tiene movimientos
(Contraloría: «todavía no se ocupa») se copia la aprobada en un borrador, se registra la exclusión
con su motivo y se aprueba. Es idempotente: si todas las cuentas ya están omitidas con ese motivo,
no crea nada.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy.orm import Session

from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.servicios.versionado_mapeo import aprobar, crear_borrador_desde, excluir_cuenta

MOTIVO_NO_SE_OCUPAN = "No se ocupan todavía (decisión de Contraloría)"


@dataclass(frozen=True)
class ResultadoOmision:
    version_numero: int | None  # la versión nueva; None si no hizo falta crear ninguna
    omitidas: list[str]  # cuentas que se agregaron o cambiaron de motivo
    ya_estaban: list[str]


def omitir_cuentas(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    editor_id: int | None,
    aprobador_id: int | None,
    cuentas: Collection[str],
    motivo: str = MOTIVO_NO_SE_OCUPAN,
    cambiar_motivo_provisional: bool = True,
) -> ResultadoOmision:
    """Crea y aprueba una versión del mapeo con `cuentas` omitidas a propósito.

    Con `cambiar_motivo_provisional`, las exclusiones que ya existían con un motivo «Provisional…»
    pasan al motivo definitivo. Lanza `LookupError` si no hay mapeo aprobado y `AprobacionBloqueada`
    si quedara otra cuenta con movimiento sin línea ni exclusión.
    """
    repo = RepositorioMapeo(db, hotel_id)
    aprobada = repo.aprobada()
    if aprobada is None:
        raise LookupError("No hay un mapeo aprobado del cual partir")
    actuales = {e.cuenta_codigo: e.motivo for e in repo.excluidas(aprobada.id)}
    pedidas = sorted({c.strip() for c in cuentas if c.strip()})
    por_hacer = [c for c in pedidas if actuales.get(c) != motivo]
    if cambiar_motivo_provisional:
        por_hacer += [
            c for c, m in actuales.items() if m.startswith("Provisional") and c not in por_hacer
        ]
    por_hacer = sorted(set(por_hacer))
    ya = [c for c in pedidas if c not in por_hacer]
    if not por_hacer:
        return ResultadoOmision(None, [], ya)

    borrador = crear_borrador_desde(
        db, organizacion_id=organizacion_id, hotel_id=hotel_id, usuario_id=editor_id
    )
    for cuenta in por_hacer:
        excluir_cuenta(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=editor_id,
            version_id=borrador.id,
            cuenta_codigo=cuenta,
            motivo=motivo,
        )
    version = aprobar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=aprobador_id,
        version_id=borrador.id,
        notas=f"Se omiten {', '.join(por_hacer)}: {motivo}",
    )
    return ResultadoOmision(version.numero, por_hacer, ya)
