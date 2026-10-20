"""Historial de una cifra (Blueprint §32, Fase 5.5): qué la ha afectado, cuándo y quién.

Junta, para una línea y un periodo: las cargas de los meses del acumulado, los cambios al mapeo
de esa línea y las versiones aprobadas, las capturas manuales, los comentarios y los cambios de
estado del cierre. Quien tiene el acceso limitado a sus secciones solo ve lo que se dijo de su
línea (comentarios, capturas y cambios de mapeo), no las cargas ni el cierre.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_REPORTE
from fpa.api.v1.tipos import FechaHoraUtc, IdRuta
from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, periodos_ytd
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.modelos.auditoria import EventoAuditoria
from fpa.modelos.cargas import CargaArchivo
from fpa.modelos.cierre import CierreTransicion
from fpa.modelos.comentarios import ComentarioLinea
from fpa.modelos.identidad import Usuario
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.acceso_secciones import exigir_linea, restriccion
from fpa.servicios.actual import version_de_mapeo
from fpa.servicios.cierre import cierre_de

router = APIRouter(tags=["variance"], responses=RESPUESTAS_REPORTE)
Lectura = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.VARIANCE_LEER))]

_CAMBIOS_MAPEO = {
    "vinculo_agregado": "Cuenta vinculada",
    "vinculo_quitado": "Cuenta desvinculada",
    "signo_cambiado": "Signo de la cuenta cambiado",
}


class HechoSalida(BaseModel):
    fecha: FechaHoraUtc
    tipo: str  # carga | mapeo | captura | comentario | cierre
    titulo: str
    detalle: str | None
    usuario: str | None


class HistorialSalida(BaseModel):
    linea_id: int
    descripcion: str
    periodo: str
    hechos: list[HechoSalida]


@router.get(
    "/hoteles/{hotel_id}/variance/lineas/{linea_id}/historial", response_model=HistorialSalida
)
def historial_de_cifra(
    linea_id: IdRuta,
    contexto: Lectura,
    periodo: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")],
    db: Session = Depends(get_db),
) -> HistorialSalida:
    exigir_linea(db, contexto, linea_id)
    try:
        mapeo = version_de_mapeo(db, contexto.hotel_id, None)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None
    lineas = RepositorioReporte(db, contexto.hotel_id).lineas(mapeo.version_estructura_id)
    linea = next((x for x in lineas if x.id == linea_id), None)
    if linea is None or linea.tipo == "seccion":
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    completo = restriccion(contexto) is None
    meses = periodos_ytd(periodo, MES_INICIO_POR_DEFECTO)
    crudos: list[tuple[datetime, str, str, str | None, int | None]] = []

    def agregar(
        fecha: datetime, tipo: str, titulo: str, detalle: str | None, uid: int | None
    ) -> None:
        crudos.append((fecha, tipo, titulo, detalle, uid))

    if completo:
        for c in db.scalars(
            select(CargaArchivo).where(
                CargaArchivo.hotel_id == contexto.hotel_id, CargaArchivo.periodo.in_(meses)
            )
        ):
            agregar(
                c.creado_en,
                "carga",
                f"Carga de {c.periodo}: {c.nombre_archivo}",
                f"{c.estado} · {c.n_movimientos} movimientos · hash {c.sha256[:12]}",
                c.usuario_id,
            )
    eventos = db.scalars(
        select(EventoAuditoria)
        .where(
            EventoAuditoria.hotel_id == contexto.hotel_id,
            EventoAuditoria.accion.in_(("mapeo.editado", "mapeo.aprobado", "actual.capturado")),
        )
        .order_by(EventoAuditoria.id)
    )
    for ev in eventos:
        d = ev.detalle or {}
        if ev.accion == "mapeo.editado" and d.get("linea_id") == linea_id:
            titulo = _CAMBIOS_MAPEO.get(str(d.get("cambio")), "Mapeo editado")
            agregar(ev.creado_en, "mapeo", f"{titulo}: {d.get('cuenta')}", None, ev.usuario_id)
        elif ev.accion == "mapeo.aprobado" and completo:
            agregar(
                ev.creado_en,
                "mapeo",
                f"Mapeo aprobado (versión {ev.entidad_id})",
                None,
                ev.usuario_id,
            )
        elif ev.accion == "actual.capturado":
            for cambio in d.get("cambios", []):
                if (
                    cambio.get("linea") == linea.descripcion.strip()
                    and cambio.get("periodo") in meses
                ):
                    agregar(
                        ev.creado_en,
                        "captura",
                        f"Actual capturado de {cambio['periodo']}",
                        f"{cambio.get('antes') or '—'} → {cambio.get('despues') or '—'}",
                        ev.usuario_id,
                    )
    for k in db.scalars(
        select(ComentarioLinea).where(
            ComentarioLinea.hotel_id == contexto.hotel_id,
            ComentarioLinea.linea_id == linea_id,
            ComentarioLinea.periodo == periodo,
            ComentarioLinea.padre_id.is_(None),
        )
    ):
        agregar(k.creado_en, "comentario", "Comentario", k.texto[:200], k.autor_id)
    if completo:
        cierre = cierre_de(db, contexto.hotel_id, periodo)
        if cierre is not None:
            for t in db.scalars(
                select(CierreTransicion)
                .where(CierreTransicion.cierre_id == cierre.id)
                .order_by(CierreTransicion.id)
            ):
                agregar(
                    t.creado_en, "cierre", f"Cierre: {t.desde} → {t.hacia}", t.nota, t.usuario_id
                )
    ids = {c[4] for c in crudos if c[4] is not None}
    nombres = {u.id: u.nombre for u in db.scalars(select(Usuario).where(Usuario.id.in_(ids)))}
    return HistorialSalida(
        linea_id=linea_id,
        descripcion=linea.descripcion,
        periodo=periodo,
        hechos=[
            HechoSalida(
                fecha=fecha,
                tipo=tipo,
                titulo=titulo,
                detalle=detalle,
                usuario=nombres.get(uid) if uid is not None else None,
            )
            for fecha, tipo, titulo, detalle, uid in sorted(crudos, key=lambda x: x[0])
        ],
    )
