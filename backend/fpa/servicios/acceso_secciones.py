"""Qué puede ver un usuario que solo tiene asignadas algunas secciones del Variance (Fase 5.2).

Un responsable de departamento ve las líneas de sus secciones, el desglose de esas líneas y los
movimientos de las cuentas vinculadas a ellas; nada más. Lo que queda fuera responde como si no
existiera (404), para no revelar qué hay en otras secciones.
"""

from __future__ import annotations

from collections.abc import Collection

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fpa.identidad.dependencias import ContextoHotel
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.actual import version_de_mapeo


def restriccion(contexto: ContextoHotel) -> frozenset[str] | None:
    """Secciones permitidas del usuario en este hotel; `None` si ve todo."""
    return contexto.principal.secciones_permitidas(contexto.hotel_id)


def exigir_acceso_completo(contexto: ContextoHotel) -> None:
    """Lo que no se puede recortar por sección (exportar, asientos): 403 si está restringido."""
    if restriccion(contexto) is not None:
        raise HTTPException(
            status_code=403, detail="Tu acceso está limitado a las secciones que tienes asignadas"
        )


def lineas_permitidas(
    db: Session, hotel_id: int, version_estructura_id: int, secciones: Collection[str]
) -> set[int]:
    """Ids de las líneas que pertenecen a las secciones indicadas (por nombre), con la sección."""
    lineas = RepositorioReporte(db, hotel_id).lineas(version_estructura_id)
    ids_seccion = {x.id for x in lineas if x.tipo == "seccion" and x.descripcion in secciones}
    return {x.id for x in lineas if x.id in ids_seccion or x.seccion_id in ids_seccion}


def exigir_linea(
    db: Session, contexto: ContextoHotel, linea_id: int, version_mapeo_id: int | None = None
) -> None:
    """404 si la línea no es de una sección asignada al usuario (no hace nada si ve todo)."""
    secciones = restriccion(contexto)
    if secciones is None:
        return
    try:
        mapeo = version_de_mapeo(db, contexto.hotel_id, version_mapeo_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Línea no encontrada") from None
    if linea_id not in lineas_permitidas(
        db, contexto.hotel_id, mapeo.version_estructura_id, secciones
    ):
        raise HTTPException(status_code=404, detail="Línea no encontrada")


def exigir_cuenta(db: Session, contexto: ContextoHotel, cuenta_codigo: str) -> None:
    """404 si la cuenta no está vinculada a ninguna línea de las secciones del usuario."""
    secciones = restriccion(contexto)
    if secciones is None:
        return
    try:
        mapeo = version_de_mapeo(db, contexto.hotel_id, None)
    except LookupError:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada") from None
    permitidas = lineas_permitidas(db, contexto.hotel_id, mapeo.version_estructura_id, secciones)
    vinculadas = {
        v.cuenta_codigo
        for v in RepositorioMapeo(db, contexto.hotel_id).vinculos(mapeo.id)
        if v.linea_id in permitidas
    }
    if cuenta_codigo not in vinculadas:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")


def ids_visibles(db: Session, contexto: ContextoHotel) -> set[int] | None:
    """Ids de las líneas que el usuario puede ver; `None` si ve todo."""
    secciones = restriccion(contexto)
    if secciones is None:
        return None
    try:
        mapeo = version_de_mapeo(db, contexto.hotel_id, None)
    except LookupError:
        return set()
    return lineas_permitidas(db, contexto.hotel_id, mapeo.version_estructura_id, secciones)
