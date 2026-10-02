"""Importación del mapeo desde el Excel y control de signos contra el catálogo oficial.

El signo con que una cuenta entra a una línea del Variance es su naturaleza (decisión tomada,
pendiente de confirmación formal de Contraloría): Deudor suma (+1) y Acreedor resta (-1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from fpa.ingesta.variance_mapeo import ResultadoMapeo, VinculoLeido
from fpa.ingesta.variance_mzt import normalizar_codigo
from fpa.modelos.base import ahora_utc
from fpa.modelos.mapeo import DESCARTADA, MapeoLineaCuenta, VersionMapeo
from fpa.modelos.reporte import VersionEstructuraReporte
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo

_SIGNO_POR_TIPO = {"Deudor": 1, "Acreedor": -1}


def signo_esperado(tipo: str | None) -> int | None:
    """Signo que corresponde a la naturaleza de la cuenta; None si no se conoce."""
    return _SIGNO_POR_TIPO.get(tipo or "")


@dataclass(frozen=True)
class DiscrepanciaSigno:
    cuenta_codigo: str
    linea_id: int
    signo_mapeo: int
    signo_esperado: int
    tipo: str


def discrepancias_de_signo(db: Session, hotel_id: int, version_id: int) -> list[DiscrepanciaSigno]:
    """Vínculos cuyo signo no coincide con el TIPO de la cuenta en el catálogo oficial."""
    tipos = {c.codigo: c.tipo for c in RepositorioCatalogo(db, hotel_id).todas()}
    salida: list[DiscrepanciaSigno] = []
    for v in RepositorioMapeo(db, hotel_id).vinculos(version_id):
        tipo = tipos.get(v.cuenta_codigo)
        esperado = signo_esperado(tipo)
        if tipo is not None and esperado is not None and esperado != v.signo:
            salida.append(DiscrepanciaSigno(v.cuenta_codigo, v.linea_id, v.signo, esperado, tipo))
    return salida


@dataclass
class ResultadoImportacionMapeo:
    resolucion: Resolucion
    version: VersionMapeo | None = None
    n_vinculos: int = 0
    lineas_vinculadas: int = 0
    sin_catalogo: list[str] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)


def importar_mapeo(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version_estructura: VersionEstructuraReporte,
    leido: ResultadoMapeo,
    archivo: DatosArchivo,
    confirmar_reemplazo: bool = False,
) -> ResultadoImportacionMapeo:
    """Crea un **borrador** de mapeo con lo que trae el Excel. El llamador hace `commit`.

    Si ya existe un borrador, pide confirmación y, al confirmar, lo descarta (queda en historial).
    """
    repo = RepositorioMapeo(db, hotel_id)
    base: dict[str, Any] = {"archivo": archivo.nombre, "sha256": archivo.sha256}

    def evento(accion: str, entidad_id: int | None, detalle: dict[str, Any]) -> None:
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion=accion,
            entidad="version_mapeo",
            entidad_id=entidad_id,
            detalle=detalle,
        )

    if version_estructura.hotel_id != hotel_id:
        raise ValueError("La versión de estructura no pertenece al hotel")
    if not leido.es_valido:
        evento("mapeo.rechazado", None, {**base, "motivos": leido.errores[:10]})
        return ResultadoImportacionMapeo(Resolucion.RECHAZADA, motivos=leido.errores)
    borrador = repo.borrador()
    if borrador is not None and not confirmar_reemplazo:
        return ResultadoImportacionMapeo(
            Resolucion.REQUIERE_CONFIRMACION,
            version=borrador,
            motivos=[
                f"Ya hay un borrador de mapeo (versión {borrador.numero}); "
                "confirma para descartarlo"
            ],
        )

    lineas = {x.orden: x for x in RepositorioReporte(db, hotel_id).lineas(version_estructura.id)}
    conocidas = {c.codigo for c in RepositorioCatalogo(db, hotel_id).todas()}
    por_clave: dict[str, set[str]] = {}
    for codigo in conocidas:
        por_clave.setdefault(normalizar_codigo(codigo), set()).add(codigo)

    def resolver(v: VinculoLeido) -> str:
        """Un código pegado como valor pierde el cero final: se completa con el catálogo."""
        if v.origen != "excel_ago" or v.cuenta_codigo in conocidas:
            return v.cuenta_codigo
        candidatos = por_clave.get(normalizar_codigo(v.cuenta_codigo), set())
        return next(iter(candidatos)) if len(candidatos) == 1 else v.cuenta_codigo

    resueltos: dict[tuple[int, str], int] = {}
    for v in leido.vinculos:
        resueltos.setdefault((v.orden, resolver(v)), v.signo)
    with db.begin_nested():
        if borrador is not None:
            borrador.estado = DESCARTADA
            borrador.cerrada_en = ahora_utc()
            db.flush()
            evento("mapeo.borrador_descartado", borrador.id, {**base, "numero": borrador.numero})
        version = VersionMapeo(
            hotel_id=hotel_id,
            numero=repo.siguiente_numero(),
            version_estructura_id=version_estructura.id,
            origen=archivo.nombre,
            creada_por_id=usuario_id,
        )
        db.add(version)
        db.flush()
        for (orden, codigo), signo in resueltos.items():
            db.add(
                MapeoLineaCuenta(
                    version_mapeo_id=version.id,
                    hotel_id=hotel_id,
                    linea_id=lineas[orden].id,
                    cuenta_codigo=codigo,
                    signo=signo,
                    origen="excel",
                )
            )
        db.flush()
        evento(
            "mapeo.borrador_creado",
            version.id,
            {
                **base,
                "numero": version.numero,
                "n_vinculos": len(resueltos),
                "lineas_vinculadas": leido.lineas_vinculadas,
            },
        )
    return ResultadoImportacionMapeo(
        Resolucion.CREADA,
        version=version,
        n_vinculos=len(resueltos),
        lineas_vinculadas=leido.lineas_vinculadas,
        sin_catalogo=sorted({codigo for _, codigo in resueltos} - conocidas),
    )
