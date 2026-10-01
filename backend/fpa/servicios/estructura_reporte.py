"""Importación de la estructura del reporte Variance.

Mismas reglas que las cargas (ADR 0003), con una estructura vigente por hotel:
- El mismo archivo (mismo SHA-256) no cambia nada -> `DUPLICADA`.
- Si ya hay una vigente de OTRO archivo, pide confirmación sin escribir -> `REQUIERE_CONFIRMACION`.
  Al confirmar, la anterior pasa a `reemplazada` (se conserva el historial) y se audita.
- Una lectura inválida se rechaza (`RECHAZADA`) y queda en la auditoría.
- Todo lo que escribe va en un SAVEPOINT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from fpa.ingesta.variance_estructura import LineaLeida, ResultadoEstructura, TipoLinea
from fpa.modelos.base import ahora_utc
from fpa.modelos.reporte import LineaReporte, VersionEstructuraReporte
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo


@dataclass
class ResultadoImportacionEstructura:
    resolucion: Resolucion
    version: VersionEstructuraReporte | None = None
    reemplazada: VersionEstructuraReporte | None = None
    motivos: list[str] = field(default_factory=list)


def importar_estructura_reporte(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    resultado: ResultadoEstructura,
    archivo: DatosArchivo,
    periodo_referencia: str | None = None,
    confirmar_reemplazo: bool = False,
) -> ResultadoImportacionEstructura:
    """No lanza excepciones por condiciones de negocio; devuelve una `Resolucion`.

    El llamador hace `commit` cuando la resolución no sea `REQUIERE_CONFIRMACION`.
    """
    repo = RepositorioReporte(db, hotel_id)
    base = {"archivo": archivo.nombre, "sha256": archivo.sha256}

    def evento(accion: str, entidad_id: int | None, detalle: dict[str, Any]) -> None:
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion=accion,
            entidad="estructura_reporte",
            entidad_id=entidad_id,
            detalle=detalle,
        )

    if not resultado.es_valido:
        evento("estructura.rechazada", None, {**base, "motivos": resultado.errores[:10]})
        return ResultadoImportacionEstructura(Resolucion.RECHAZADA, motivos=resultado.errores)

    vigente = repo.vigente()
    if vigente is not None and vigente.sha256 == archivo.sha256:
        evento("estructura.duplicada", vigente.id, base)
        return ResultadoImportacionEstructura(Resolucion.DUPLICADA, version=vigente)
    if vigente is not None and not confirmar_reemplazo:
        return ResultadoImportacionEstructura(
            Resolucion.REQUIERE_CONFIRMACION,
            reemplazada=vigente,
            motivos=[
                f"Ya hay una estructura vigente ({vigente.nombre_archivo}, "
                f"{vigente.n_lineas} líneas); confirma para reemplazarla"
            ],
        )

    with db.begin_nested():
        if vigente is not None:
            vigente.estado = "reemplazada"
            vigente.reemplazada_en = ahora_utc()
            db.flush()  # libera el índice de "una vigente por hotel" antes de insertar
        version = VersionEstructuraReporte(
            hotel_id=hotel_id,
            nombre_archivo=archivo.nombre,
            sha256=archivo.sha256,
            periodo_referencia=periodo_referencia,
            estado="vigente",
            n_lineas=len(resultado.lineas),
            n_detalle=resultado.contar(TipoLinea.DETALLE),
            controles={"avisos": resultado.avisos},
            usuario_id=usuario_id,
        )
        db.add(version)
        db.flush()

        por_orden: dict[int, LineaReporte] = {}
        # Las secciones primero, para poder apuntarles con `seccion_id`
        for linea in resultado.lineas:
            if linea.tipo is TipoLinea.SECCION:
                modelo = _modelo(version, hotel_id, linea, None)
                db.add(modelo)
                por_orden[linea.orden] = modelo
        db.flush()
        for linea in resultado.lineas:
            if linea.tipo is not TipoLinea.SECCION:
                seccion = por_orden.get(linea.seccion_orden) if linea.seccion_orden else None
                db.add(_modelo(version, hotel_id, linea, seccion.id if seccion else None))
        db.flush()
        evento(
            "estructura.creada",
            version.id,
            {
                **base,
                "periodo_referencia": periodo_referencia,
                "n_lineas": version.n_lineas,
                "n_detalle": version.n_detalle,
            },
        )
        if vigente is not None:
            evento(
                "estructura.reemplazada",
                vigente.id,
                {
                    **base,
                    "reemplazada_por_id": version.id,
                    "archivo_anterior": vigente.nombre_archivo,
                },
            )
    return ResultadoImportacionEstructura(
        Resolucion.REEMPLAZADA if vigente is not None else Resolucion.CREADA,
        version=version,
        reemplazada=vigente,
    )


def _modelo(
    version: VersionEstructuraReporte, hotel_id: int, linea: LineaLeida, seccion_id: int | None
) -> LineaReporte:
    return LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=linea.orden,
        tipo=linea.tipo.value,
        nivel=linea.nivel,
        seccion_id=seccion_id,
        codigo_corporativo=linea.codigo_corporativo,
        descripcion=linea.descripcion,
        clave=linea.clave,
        fila_origen=linea.fila_origen,
    )
