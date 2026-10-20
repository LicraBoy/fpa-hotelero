"""Comentarios por línea y periodo, con hilo, responsable, estatus y evidencia (Fase 5.3).

Reglas:
- Un comentario es por línea + periodo + bloque (mes o acumulado). El primero del hilo trae el
  responsable y el estatus (pendiente → explicado → aprobado); las respuestas solo traen texto.
- Quien tiene el acceso limitado a sus secciones solo ve y comenta líneas de esas secciones.
- Editar el texto solo lo hace su autor y deja la versión anterior en el historial.
- Pasar a «aprobado» (o volver de él) exige `comentario:resolver`.
- El texto se guarda tal cual y la pantalla lo muestra como texto: nunca como HTML.
- Los adjuntos se validan por contenido, se guardan en disco bajo su hash y se descargan siempre
  como archivo, nunca para abrirse en el navegador.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_REPORTE
from fpa.api.v1.tipos import ID_MAX, IdRuta
from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso, rol_tiene_permiso
from fpa.modelos.base import ahora_utc
from fpa.modelos.comentarios import (
    AdjuntoComentario,
    ComentarioLinea,
    ComentarioRevision,
)
from fpa.modelos.identidad import Asignacion, Usuario
from fpa.repositorios.reporte import RepositorioReporte
from fpa.seguridad.archivos import (
    ArchivoRechazado,
    LimitesArchivo,
    guardar_en_temporal,
    inspeccionar_evidencia,
    nombre_seguro,
    verificar_nombre_evidencia,
)
from fpa.servicios.acceso_secciones import ids_visibles
from fpa.servicios.actual import version_de_mapeo
from fpa.servicios.auditoria import auditar
from fpa.servicios.cierre import estado_de

router = APIRouter(tags=["comentarios"], responses=RESPUESTAS_REPORTE)

Leer = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.COMENTARIO_LEER))]
Crear = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.COMENTARIO_CREAR))]
PATRON_PERIODO = r"^20\d{2}-(0[1-9]|1[0-2])$"
Periodo = Annotated[str, Query(pattern=PATRON_PERIODO, description="AAAA-MM")]
Bloque = Literal["mes", "ytd"]
Estatus = Literal["pendiente", "explicado", "aprobado"]
MAX_TEXTO = 2000


def _texto_valido(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("El comentario no puede estar vacío")
    if len(v) > MAX_TEXTO:
        raise ValueError(f"El comentario admite hasta {MAX_TEXTO} caracteres")
    return v


class AdjuntoSalida(BaseModel):
    id: int
    nombre: str
    tamano: int
    autor: str
    creado_en: str


class RespuestaSalida(BaseModel):
    id: int
    texto: str
    autor_id: int
    autor: str
    creado_en: str
    editado: bool


class ComentarioSalida(BaseModel):
    id: int
    linea_id: int
    linea_descripcion: str
    periodo: str
    bloque: str
    texto: str
    autor_id: int
    autor: str
    responsable_id: int | None
    responsable: str | None
    estatus: str
    creado_en: str
    actualizado_en: str
    editado: bool
    adjuntos: list[AdjuntoSalida]
    respuestas: list[RespuestaSalida]


class ListaComentarios(BaseModel):
    comentarios: list[ComentarioSalida]
    # personas a quienes se puede asignar un comentario (con acceso a la lectura del reporte)
    asignables: dict[int, str]
    puede_resolver: bool


class ConteoLinea(BaseModel):
    total: int
    pendientes: int


class Conteos(BaseModel):
    # linea_id -> bloque -> conteo (solo hilos, no respuestas)
    por_linea: dict[int, dict[str, ConteoLinea]]


class ComentarioNuevo(BaseModel):
    linea_id: int = Field(ge=1, le=ID_MAX)
    periodo: str = Field(pattern=PATRON_PERIODO)
    bloque: Bloque
    texto: str
    responsable_id: int | None = Field(default=None, ge=1, le=ID_MAX)

    _t = field_validator("texto")(_texto_valido)


class TextoNuevo(BaseModel):
    texto: str

    _t = field_validator("texto")(_texto_valido)


class CambioEstatus(BaseModel):
    estatus: Estatus


class CambioResponsable(BaseModel):
    responsable_id: int | None = Field(ge=1, le=ID_MAX)


def _nombres(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {u.id: u.nombre for u in db.scalars(select(Usuario).where(Usuario.id.in_(ids)))}


def _iso(momento: datetime) -> str:
    return momento.isoformat()


def _asignables(db: Session, contexto: ContextoHotel) -> dict[int, str]:
    """Quienes tienen acceso al hotel y pueden leer comentarios (activos, de la organización)."""
    filas = db.execute(
        select(Usuario, Asignacion)
        .join(Asignacion, Asignacion.usuario_id == Usuario.id)
        .where(
            Asignacion.hotel_id == contexto.hotel_id,
            Usuario.organizacion_id == contexto.organizacion_id,
            Usuario.activo.is_(True),
        )
        .order_by(Usuario.nombre)
    ).all()
    # Solo quien puede escribir comentarios tiene sentido como responsable
    from fpa.modelos.identidad import Rol

    roles = {r.id: r.codigo for r in db.scalars(select(Rol))}
    return {
        u.id: u.nombre
        for u, a in filas
        if rol_tiene_permiso(roles[a.rol_id], Permiso.COMENTARIO_CREAR)
    }


def _hilo(db: Session, contexto: ContextoHotel, raiz_id: int) -> ComentarioLinea:
    """El comentario raíz de ese hotel y visible para el usuario; 404 si no."""
    raiz = db.scalar(
        select(ComentarioLinea).where(
            ComentarioLinea.id == raiz_id,
            ComentarioLinea.hotel_id == contexto.hotel_id,
            ComentarioLinea.padre_id.is_(None),
        )
    )
    visibles = ids_visibles(db, contexto)
    if raiz is None or (visibles is not None and raiz.linea_id not in visibles):
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    return raiz


def _exigir_no_bloqueado(db: Session, contexto: ContextoHotel, periodo: str) -> None:
    if estado_de(db, contexto.hotel_id, periodo) == "bloqueado":
        raise HTTPException(
            status_code=409, detail=f"El cierre de {periodo} está bloqueado: ya no admite cambios"
        )


def _armar(db: Session, raices: list[ComentarioLinea]) -> list[ComentarioSalida]:
    if not raices:
        return []
    ids = [r.id for r in raices]
    respuestas = list(
        db.scalars(
            select(ComentarioLinea)
            .where(ComentarioLinea.padre_id.in_(ids))
            .order_by(ComentarioLinea.creado_en, ComentarioLinea.id)
        )
    )
    todos = ids + [r.id for r in respuestas]
    editados = {
        cid
        for cid, n in db.execute(
            select(ComentarioRevision.comentario_id, func.count())
            .where(ComentarioRevision.comentario_id.in_(todos))
            .group_by(ComentarioRevision.comentario_id)
        )
        if n > 1
    }
    adjuntos = list(
        db.scalars(
            select(AdjuntoComentario)
            .where(AdjuntoComentario.comentario_id.in_(ids))
            .order_by(AdjuntoComentario.id)
        )
    )
    personas = {r.autor_id for r in raices + respuestas} | {
        r.responsable_id for r in raices if r.responsable_id
    }
    personas |= {a.usuario_id for a in adjuntos}
    nombres = _nombres(db, personas)
    salida = []
    for r in raices:
        salida.append(
            ComentarioSalida(
                id=r.id,
                linea_id=r.linea_id,
                linea_descripcion=r.linea_descripcion,
                periodo=r.periodo,
                bloque=r.bloque,
                texto=r.texto,
                autor_id=r.autor_id,
                autor=nombres.get(r.autor_id, "—"),
                responsable_id=r.responsable_id,
                responsable=nombres.get(r.responsable_id) if r.responsable_id else None,
                estatus=r.estatus or "pendiente",
                creado_en=_iso(r.creado_en),
                actualizado_en=_iso(r.actualizado_en),
                editado=r.id in editados,
                adjuntos=[
                    AdjuntoSalida(
                        id=a.id,
                        nombre=a.nombre,
                        tamano=a.tamano,
                        autor=nombres.get(a.usuario_id, "—"),
                        creado_en=_iso(a.creado_en),
                    )
                    for a in adjuntos
                    if a.comentario_id == r.id
                ],
                respuestas=[
                    RespuestaSalida(
                        id=x.id,
                        texto=x.texto,
                        autor_id=x.autor_id,
                        autor=nombres.get(x.autor_id, "—"),
                        creado_en=_iso(x.creado_en),
                        editado=x.id in editados,
                    )
                    for x in respuestas
                    if x.padre_id == r.id
                ],
            )
        )
    return salida


@router.get("/hoteles/{hotel_id}/comentarios", response_model=ListaComentarios)
def listar(
    contexto: Leer,
    periodo: Periodo,
    linea_id: Annotated[int | None, Query(ge=1, le=ID_MAX)] = None,
    bloque: Bloque | None = None,
    db: Session = Depends(get_db),
) -> ListaComentarios:
    consulta = select(ComentarioLinea).where(
        ComentarioLinea.hotel_id == contexto.hotel_id,
        ComentarioLinea.periodo == periodo,
        ComentarioLinea.padre_id.is_(None),
    )
    if linea_id is not None:
        consulta = consulta.where(ComentarioLinea.linea_id == linea_id)
    if bloque is not None:
        consulta = consulta.where(ComentarioLinea.bloque == bloque)
    raices = list(db.scalars(consulta.order_by(ComentarioLinea.creado_en, ComentarioLinea.id)))
    visibles = ids_visibles(db, contexto)
    if visibles is not None:
        raices = [r for r in raices if r.linea_id in visibles]
    rol = contexto.principal.roles_por_hotel[contexto.hotel_id]
    return ListaComentarios(
        comentarios=_armar(db, raices),
        asignables=_asignables(db, contexto),
        puede_resolver=rol_tiene_permiso(rol, Permiso.COMENTARIO_RESOLVER),
    )


@router.get("/hoteles/{hotel_id}/comentarios/conteos", response_model=Conteos)
def conteos(contexto: Leer, periodo: Periodo, db: Session = Depends(get_db)) -> Conteos:
    """Cuántos hilos hay por línea y bloque (para el indicador de la tabla del Variance)."""
    raices = db.scalars(
        select(ComentarioLinea).where(
            ComentarioLinea.hotel_id == contexto.hotel_id,
            ComentarioLinea.periodo == periodo,
            ComentarioLinea.padre_id.is_(None),
        )
    )
    visibles = ids_visibles(db, contexto)
    por_linea: dict[int, dict[str, ConteoLinea]] = {}
    for r in raices:
        if visibles is not None and r.linea_id not in visibles:
            continue
        c = por_linea.setdefault(r.linea_id, {}).setdefault(
            r.bloque, ConteoLinea(total=0, pendientes=0)
        )
        c.total += 1
        if (r.estatus or "pendiente") == "pendiente":
            c.pendientes += 1
    return Conteos(por_linea=por_linea)


def _validar_responsable(db: Session, contexto: ContextoHotel, responsable_id: int | None) -> None:
    if responsable_id is None:
        return
    if responsable_id not in _asignables(db, contexto):
        raise HTTPException(
            status_code=422, detail="Esa persona no puede ser responsable en este hotel"
        )


@router.post("/hoteles/{hotel_id}/comentarios", response_model=ComentarioSalida, status_code=201)
def crear(
    entrada: ComentarioNuevo, contexto: Crear, db: Session = Depends(get_db)
) -> ComentarioSalida:
    try:
        mapeo = version_de_mapeo(db, contexto.hotel_id, None)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None
    lineas = {
        x.id: x
        for x in RepositorioReporte(db, contexto.hotel_id).lineas(mapeo.version_estructura_id)
    }
    linea = lineas.get(entrada.linea_id)
    visibles = ids_visibles(db, contexto)
    if (
        linea is None
        or linea.tipo == "seccion"
        or (visibles is not None and linea.id not in visibles)
    ):
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    _exigir_no_bloqueado(db, contexto, entrada.periodo)
    _validar_responsable(db, contexto, entrada.responsable_id)
    ahora = ahora_utc()
    comentario = ComentarioLinea(
        hotel_id=contexto.hotel_id,
        linea_id=linea.id,
        linea_descripcion=linea.descripcion,
        periodo=entrada.periodo,
        bloque=entrada.bloque,
        texto=entrada.texto,
        autor_id=contexto.principal.usuario_id,
        responsable_id=entrada.responsable_id,
        estatus="pendiente",
        creado_en=ahora,
        actualizado_en=ahora,
    )
    db.add(comentario)
    db.flush()
    db.add(
        ComentarioRevision(
            comentario_id=comentario.id,
            texto=entrada.texto,
            usuario_id=contexto.principal.usuario_id,
            creado_en=ahora,
        )
    )
    _auditar(db, contexto, "comentario.creado", comentario, {"linea": linea.descripcion})
    db.commit()
    return _armar(db, [comentario])[0]


def _auditar(
    db: Session,
    contexto: ContextoHotel,
    accion: str,
    comentario: ComentarioLinea,
    extra: dict[str, object] | None = None,
) -> None:
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion=accion,
        entidad="comentario",
        entidad_id=comentario.id,
        detalle={
            "linea_id": comentario.linea_id,
            "periodo": comentario.periodo,
            "bloque": comentario.bloque,
            **(extra or {}),
        },
    )


@router.post(
    "/hoteles/{hotel_id}/comentarios/{comentario_id}/respuestas",
    response_model=ComentarioSalida,
    status_code=201,
)
def responder(
    comentario_id: IdRuta, entrada: TextoNuevo, contexto: Crear, db: Session = Depends(get_db)
) -> ComentarioSalida:
    raiz = _hilo(db, contexto, comentario_id)
    _exigir_no_bloqueado(db, contexto, raiz.periodo)
    ahora = ahora_utc()
    respuesta = ComentarioLinea(
        hotel_id=raiz.hotel_id,
        linea_id=raiz.linea_id,
        linea_descripcion=raiz.linea_descripcion,
        periodo=raiz.periodo,
        bloque=raiz.bloque,
        padre_id=raiz.id,
        texto=entrada.texto,
        autor_id=contexto.principal.usuario_id,
        creado_en=ahora,
        actualizado_en=ahora,
    )
    db.add(respuesta)
    db.flush()
    db.add(
        ComentarioRevision(
            comentario_id=respuesta.id,
            texto=entrada.texto,
            usuario_id=contexto.principal.usuario_id,
            creado_en=ahora,
        )
    )
    raiz.actualizado_en = ahora
    _auditar(db, contexto, "comentario.respondido", raiz, {"respuesta_id": respuesta.id})
    db.commit()
    return _armar(db, [raiz])[0]


@router.patch(
    "/hoteles/{hotel_id}/comentarios/{comentario_id}",
    response_model=ComentarioSalida,
    responses={403: {"description": "Solo el autor edita su comentario"}},
)
def editar(
    comentario_id: IdRuta, entrada: TextoNuevo, contexto: Crear, db: Session = Depends(get_db)
) -> ComentarioSalida:
    """Cambia el texto del comentario raíz o de una respuesta; la versión anterior se conserva."""
    objetivo = db.scalar(
        select(ComentarioLinea).where(
            ComentarioLinea.id == comentario_id, ComentarioLinea.hotel_id == contexto.hotel_id
        )
    )
    if objetivo is None:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    raiz = _hilo(db, contexto, objetivo.padre_id or objetivo.id)
    _exigir_no_bloqueado(db, contexto, raiz.periodo)
    if objetivo.autor_id != contexto.principal.usuario_id:
        raise HTTPException(status_code=403, detail="Solo el autor puede editar su comentario")
    if entrada.texto != objetivo.texto:
        ahora = ahora_utc()
        db.add(
            ComentarioRevision(
                comentario_id=objetivo.id,
                texto=entrada.texto,
                usuario_id=contexto.principal.usuario_id,
                creado_en=ahora,
            )
        )
        objetivo.texto = entrada.texto
        objetivo.actualizado_en = ahora
        raiz.actualizado_en = ahora
        _auditar(db, contexto, "comentario.editado", raiz, {"editado_id": objetivo.id})
        db.commit()
    return _armar(db, [raiz])[0]


@router.put(
    "/hoteles/{hotel_id}/comentarios/{comentario_id}/estatus", response_model=ComentarioSalida
)
def cambiar_estatus(
    comentario_id: IdRuta, entrada: CambioEstatus, contexto: Crear, db: Session = Depends(get_db)
) -> ComentarioSalida:
    raiz = _hilo(db, contexto, comentario_id)
    _exigir_no_bloqueado(db, contexto, raiz.periodo)
    actual = raiz.estatus or "pendiente"
    if entrada.estatus != actual:
        rol = contexto.principal.roles_por_hotel[contexto.hotel_id]
        resuelve = rol_tiene_permiso(rol, Permiso.COMENTARIO_RESOLVER)
        implicado = contexto.principal.usuario_id in (raiz.autor_id, raiz.responsable_id)
        if "aprobado" in (actual, entrada.estatus):
            if not resuelve:
                raise HTTPException(
                    status_code=403, detail="Solo Contraloría aprueba o reabre una explicación"
                )
        elif not (implicado or resuelve):
            raise HTTPException(
                status_code=403, detail="Solo el autor o el responsable cambian el estatus"
            )
        raiz.estatus = entrada.estatus
        raiz.actualizado_en = ahora_utc()
        _auditar(
            db, contexto, "comentario.estatus", raiz, {"antes": actual, "despues": entrada.estatus}
        )
        db.commit()
    return _armar(db, [raiz])[0]


@router.put(
    "/hoteles/{hotel_id}/comentarios/{comentario_id}/responsable", response_model=ComentarioSalida
)
def asignar_responsable(
    comentario_id: IdRuta,
    entrada: CambioResponsable,
    contexto: Crear,
    db: Session = Depends(get_db),
) -> ComentarioSalida:
    raiz = _hilo(db, contexto, comentario_id)
    _exigir_no_bloqueado(db, contexto, raiz.periodo)
    rol = contexto.principal.roles_por_hotel[contexto.hotel_id]
    if contexto.principal.usuario_id != raiz.autor_id and not rol_tiene_permiso(
        rol, Permiso.COMENTARIO_RESOLVER
    ):
        raise HTTPException(
            status_code=403, detail="Solo el autor o Contraloría asignan al responsable"
        )
    _validar_responsable(db, contexto, entrada.responsable_id)
    if entrada.responsable_id != raiz.responsable_id:
        antes = raiz.responsable_id
        raiz.responsable_id = entrada.responsable_id
        raiz.actualizado_en = ahora_utc()
        _auditar(
            db,
            contexto,
            "comentario.responsable",
            raiz,
            {"antes": antes, "despues": entrada.responsable_id},
        )
        db.commit()
    return _armar(db, [raiz])[0]


# --- Adjuntos -----------------------------------------------------------------------------------


def _ruta_adjunto(hotel_id: int, sha256: str, extension: str) -> Path:
    # solo un entero, un hash hexadecimal y una extensión de lista fija: no se sale de storage/
    return Path(settings.storage_dir) / "adjuntos" / str(hotel_id) / f"{sha256}{extension}"


@router.post(
    "/hoteles/{hotel_id}/comentarios/{comentario_id}/adjuntos",
    response_model=ComentarioSalida,
    status_code=201,
    responses={
        413: {"description": "Archivo demasiado grande"},
        415: {"description": "Tipo no válido"},
    },
)
def adjuntar(
    comentario_id: IdRuta,
    archivo: Annotated[UploadFile, File(description="PDF, PNG, JPG o .xlsx")],
    contexto: Crear,
    db: Session = Depends(get_db),
) -> ComentarioSalida:
    raiz = _hilo(db, contexto, comentario_id)
    _exigir_no_bloqueado(db, contexto, raiz.periodo)
    ya = db.scalar(
        select(func.count())
        .select_from(AdjuntoComentario)
        .where(AdjuntoComentario.comentario_id == raiz.id)
    )
    if (ya or 0) >= settings.adjuntos_max_por_comentario:
        raise HTTPException(
            status_code=409,
            detail=f"Máximo {settings.adjuntos_max_por_comentario} archivos por comentario",
        )
    limites = LimitesArchivo(
        max_bytes=settings.adjunto_max_bytes,
        zip_max_entradas=settings.zip_max_entradas,
        zip_max_descomprimido=settings.zip_max_descomprimido,
        zip_max_razon=settings.zip_max_razon,
    )
    nombre = nombre_seguro(archivo.filename)
    temporal: Path | None = None
    try:
        try:
            extension = verificar_nombre_evidencia(nombre)
            temporal, sha256, tamano = guardar_en_temporal(
                archivo.file, Path(settings.storage_dir) / "tmp", limites, sufijo=extension
            )
            inspeccionar_evidencia(temporal, extension, limites)
        except ArchivoRechazado as e:
            auditar(
                db,
                organizacion_id=contexto.organizacion_id,
                hotel_id=contexto.hotel_id,
                usuario_id=contexto.principal.usuario_id,
                accion="comentario.adjunto_rechazado",
                entidad="comentario",
                entidad_id=raiz.id,
                detalle={"archivo": nombre, "motivo": e.detalle, "http": e.status_code},
            )
            db.commit()
            raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
        destino = _ruta_adjunto(contexto.hotel_id, sha256, extension)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists():
            temporal.replace(destino)
        adjunto = AdjuntoComentario(
            comentario_id=raiz.id,
            hotel_id=contexto.hotel_id,
            nombre=nombre,
            extension=extension,
            sha256=sha256,
            tamano=tamano,
            usuario_id=contexto.principal.usuario_id,
        )
        db.add(adjunto)
        db.flush()
        raiz.actualizado_en = ahora_utc()
        _auditar(db, contexto, "comentario.adjunto", raiz, {"archivo": nombre, "sha256": sha256})
        db.commit()
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return _armar(db, [raiz])[0]


@router.get(
    "/hoteles/{hotel_id}/comentarios/{comentario_id}/adjuntos/{adjunto_id}",
    response_class=FileResponse,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def descargar(
    comentario_id: IdRuta, adjunto_id: IdRuta, contexto: Leer, db: Session = Depends(get_db)
) -> FileResponse:
    raiz = _hilo(db, contexto, comentario_id)
    adjunto = db.scalar(
        select(AdjuntoComentario).where(
            AdjuntoComentario.id == adjunto_id,
            AdjuntoComentario.comentario_id == raiz.id,
            AdjuntoComentario.hotel_id == contexto.hotel_id,
        )
    )
    if adjunto is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    ruta = _ruta_adjunto(adjunto.hotel_id, adjunto.sha256, adjunto.extension)
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="El archivo ya no está disponible")
    seguro = re.sub(r"[^0-9A-Za-z]", "", str(adjunto.id)) or "0"
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="comentario.adjunto_descargado",
        entidad="comentario",
        entidad_id=raiz.id,
        detalle={"adjunto_id": adjunto.id},
    )
    db.commit()
    return FileResponse(
        ruta,
        media_type="application/octet-stream",
        filename=f"evidencia-{seguro}{adjunto.extension}",
        content_disposition_type="attachment",
    )
