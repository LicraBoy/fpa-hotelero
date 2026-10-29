"""Vincular cuentas a las líneas de una sección del reporte, como una versión nueva del mapeo.

Una versión aprobada del mapeo **no se edita**: se copia la aprobada en un borrador, se agregan los
vínculos pedidos (con su nota opcional, p. ej. «No se utiliza») y se aprueba. Una cuenta que
estaba excluida «a propósito» y ahora recibe línea deja de estar excluida. Es idempotente: si todos
los vínculos ya existen con ese signo y esa nota, no crea nada.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.versionado_mapeo import (
    agregar_vinculo,
    aprobar,
    crear_borrador_desde,
    quitar_vinculo,
)


@dataclass(frozen=True)
class VinculoPedido:
    linea: (
        str  # descripción de la línea dentro de la sección (sin distinguir espacios ni mayúsculas)
    )
    cuenta: str
    nota: str | None = None
    signo: int = 1


@dataclass(frozen=True)
class ResultadoVinculos:
    version_numero: int | None  # la versión nueva; None si no hizo falta crear ninguna
    agregados: list[str] = field(default_factory=list)
    ya_estaban: list[str] = field(default_factory=list)
    exclusiones_quitadas: list[str] = field(default_factory=list)
    vinculos_quitados: list[str] = field(default_factory=list)


def _norma(texto: str) -> str:
    """Compara descripciones sin espacios ni mayúsculas (hay títulos como «A l l o c a t e d»)."""
    return "".join(texto.split()).casefold()


def vincular_cuentas(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    editor_id: int | None,
    aprobador_id: int | None,
    seccion: str,
    pedidos: Sequence[VinculoPedido],
    notas: str | None = None,
    quitar: Sequence[VinculoPedido] = (),
) -> ResultadoVinculos:
    """Crea y aprueba una versión del mapeo con los vínculos pedidos en `seccion`.

    `quitar`: vínculos que la versión nueva ya no trae (para **mover** una cuenta de una línea a
    otra: se quita de una y se pide en la otra). Quitar uno que ya no existe no hace nada.

    Lanza `LookupError` si no hay mapeo aprobado, la sección o una línea no existen (o su nombre es
    ambiguo) y `AprobacionBloqueada` si quedara una cuenta con movimiento sin línea ni exclusión.
    """
    repo = RepositorioMapeo(db, hotel_id)
    aprobada = repo.aprobada()
    if aprobada is None:
        raise LookupError("No hay un mapeo aprobado del cual partir")
    lineas = RepositorioReporte(db, hotel_id).lineas(aprobada.version_estructura_id)
    # «Store#2» = la segunda sección con ese nombre del reporte (ventas y gastos comparten título)
    nombre_seccion, _, n = seccion.partition("#")
    secciones = sorted(
        (x for x in lineas if x.tipo == "seccion" and _norma(x.descripcion) == _norma(nombre_seccion)),
        key=lambda x: x.orden,
    )
    if n.isdigit():
        secciones = [secciones[int(n) - 1]] if 1 <= int(n) <= len(secciones) else []
    if len(secciones) != 1:
        raise LookupError(f"La sección «{seccion}» no existe o es ambigua")
    en_seccion: dict[str, list[int]] = {}
    for x in lineas:
        if x.seccion_id == secciones[0].id and x.tipo == "detalle":
            en_seccion.setdefault(_norma(x.descripcion), []).append(x.id)

    existentes = {(v.linea_id, v.cuenta_codigo): v for v in repo.vinculos(aprobada.id)}
    excluidas = {e.cuenta_codigo for e in repo.excluidas(aprobada.id)}
    por_hacer: list[tuple[int, VinculoPedido]] = []
    ya: list[str] = []
    for p in pedidos:
        ids = en_seccion.get(_norma(p.linea), [])
        if len(ids) != 1:
            raise LookupError(f"La línea «{p.linea}» no existe en «{seccion}» o es ambigua")
        actual = existentes.get((ids[0], p.cuenta))
        if (
            actual is not None
            and actual.signo == p.signo
            and (actual.nota or None) == (p.nota or None)
        ):
            ya.append(f"{p.cuenta} → {p.linea}")
        else:
            por_hacer.append((ids[0], p))
    por_quitar: list[tuple[int, VinculoPedido]] = []
    for p in quitar:
        ids = en_seccion.get(_norma(p.linea), [])
        if len(ids) != 1:
            raise LookupError(f"La línea «{p.linea}» no existe en «{seccion}» o es ambigua")
        if (ids[0], p.cuenta) in existentes:
            por_quitar.append((ids[0], p))
    if not por_hacer and not por_quitar:
        return ResultadoVinculos(None, [], ya, [])

    borrador = crear_borrador_desde(
        db, organizacion_id=organizacion_id, hotel_id=hotel_id, usuario_id=editor_id
    )
    for linea_id, p in por_quitar:
        quitar_vinculo(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=editor_id,
            version_id=borrador.id,
            linea_id=linea_id,
            cuenta_codigo=p.cuenta,
        )
    for linea_id, p in por_hacer:
        agregar_vinculo(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=editor_id,
            version_id=borrador.id,
            linea_id=linea_id,
            cuenta_codigo=p.cuenta,
            signo=p.signo,
            nota=p.nota,
        )
    agregados = [f"{p.cuenta} → {p.linea}" for _, p in por_hacer]
    retirados = [f"{p.cuenta} ← {p.linea}" for _, p in por_quitar]
    quitadas = sorted({p.cuenta for _, p in por_hacer} & excluidas)
    version = aprobar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=aprobador_id,
        version_id=borrador.id,
        notas=notas or f"Se vinculan {len(agregados)} cuentas en «{seccion}»",
    )
    return ResultadoVinculos(version.numero, agregados, ya, quitadas, retirados)
