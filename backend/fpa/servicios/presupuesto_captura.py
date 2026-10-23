"""Captura por área del Budget (Fase 7.2).

Cada línea de detalle de la estructura congelada de un `CicloPresupuesto` tiene una
`LineaPresupuestoCaptura`, precargada al crear el ciclo (`inicializar_capturas`, llamada desde
`fpa.servicios.presupuesto_ciclo.crear_ciclo`). El responsable de departamento solo captura
`propuesta_anual` en las líneas de su sección — el alcance real se resuelve en cada petición con
`lineas_visibles_de` (reusa `fpa.servicios.acceso_secciones.lineas_permitidas` sin tocarlo, sobre la
estructura del ciclo en vez de la del mapeo); `responsable_id` en el modelo es solo informativo,
porque `AsignacionDepartamento` no impide varios responsables por sección.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fpa.identidad.dependencias import ContextoHotel
from fpa.modelos.identidad import AsignacionDepartamento
from fpa.modelos.presupuesto import (
    CicloPresupuesto,
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
)
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.acceso_secciones import lineas_permitidas
from fpa.servicios.auditoria import auditar


class CapturaInvalida(Exception):
    """Captura no permitida en este momento del ciclo. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


_PORCENTAJE = Decimal("0.01")


@dataclass(frozen=True)
class ResumenSeccion:
    seccion: str | None
    total_lineas: int
    lineas_capturadas: int
    cobertura_pct: Decimal
    suma_objetivo: Decimal
    suma_propuesta: Decimal


@dataclass(frozen=True)
class ResumenCiclo:
    total_lineas: int
    lineas_capturadas: int
    cobertura_pct: Decimal
    suma_objetivo: Decimal
    suma_propuesta: Decimal
    por_seccion: list[ResumenSeccion]


@dataclass(frozen=True)
class PuntoMensualCiclo:
    periodo: str
    propuesta: Decimal


@dataclass(frozen=True)
class SeccionMensualCiclo:
    seccion: str | None
    por_periodo: list[PuntoMensualCiclo]


@dataclass(frozen=True)
class ResumenMensualCiclo:
    por_periodo: list[PuntoMensualCiclo]
    lineas_sin_mensualizar: int
    por_seccion: list[SeccionMensualCiclo]


def _responsable_de_seccion(db: Session, *, hotel_id: int, seccion: str | None) -> int | None:
    if seccion is None:
        return None
    usuarios = list(
        db.scalars(
            select(AsignacionDepartamento.usuario_id).where(
                AsignacionDepartamento.hotel_id == hotel_id,
                AsignacionDepartamento.seccion == seccion,
            )
        )
    )
    return usuarios[0] if len(usuarios) == 1 else None


def inicializar_capturas(db: Session, *, ciclo: CicloPresupuesto) -> list[LineaPresupuestoCaptura]:
    """Crea una `LineaPresupuestoCaptura` por línea de detalle de la estructura del ciclo.

    Idempotente (protegido también por `UniqueConstraint("ciclo_id", "linea_id")`): las líneas que
    ya tengan su captura no se tocan.
    """
    if ciclo.version_estructura_id is None:
        raise CapturaInvalida(409, "El ciclo no tiene una estructura de reporte asociada")
    lineas = RepositorioReporte(db, ciclo.hotel_id).lineas(ciclo.version_estructura_id)
    existentes = set(
        db.scalars(
            select(LineaPresupuestoCaptura.linea_id).where(
                LineaPresupuestoCaptura.ciclo_id == ciclo.id
            )
        )
    )
    nombres_seccion = {x.id: x.descripcion for x in lineas if x.tipo == "seccion"}
    nuevas = []
    for linea in lineas:
        if linea.tipo != "detalle" or linea.id in existentes:
            continue
        seccion = nombres_seccion.get(linea.seccion_id) if linea.seccion_id else None
        responsable_id = _responsable_de_seccion(db, hotel_id=ciclo.hotel_id, seccion=seccion)
        captura = LineaPresupuestoCaptura(
            ciclo_id=ciclo.id,
            linea_id=linea.id,
            responsable_id=responsable_id,
            estado="pendiente",
        )
        db.add(captura)
        nuevas.append(captura)
    db.flush()
    return nuevas


def lineas_visibles_de(
    db: Session, contexto: ContextoHotel, ciclo: CicloPresupuesto
) -> set[int] | None:
    """Ids de línea que el usuario puede capturar en este ciclo; `None` si no está restringido."""
    secciones = contexto.principal.secciones_permitidas(contexto.hotel_id)
    if secciones is None:
        return None
    if ciclo.version_estructura_id is None:
        return set()
    return lineas_permitidas(db, contexto.hotel_id, ciclo.version_estructura_id, secciones)


def capturar_propuesta(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    propuesta_anual: Decimal | None,
    nota: str | None,
    visibles: set[int] | None,
) -> LineaPresupuestoCaptura:
    """Fija `propuesta_anual`/`nota` de una línea. `LookupError` si no existe o está fuera de
    alcance (no se distingue, para no revelar qué hay en otras secciones)."""
    ciclo = db.get(CicloPresupuesto, ciclo_id)
    if ciclo is None or ciclo.hotel_id != hotel_id:
        raise LookupError("Ciclo de presupuesto no encontrado")
    if visibles is not None and linea_id not in visibles:
        raise LookupError("Línea de captura no encontrada")
    captura = db.scalar(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo_id,
            LineaPresupuestoCaptura.linea_id == linea_id,
        )
    )
    if captura is None:
        raise LookupError("Línea de captura no encontrada")
    if ciclo.estado != "borrador":
        raise CapturaInvalida(409, "El ciclo no está en captura")
    nota = (nota or "").strip() or None
    if nota is not None and len(nota) > 1000:
        raise CapturaInvalida(422, "La nota admite hasta 1000 caracteres")
    cambio = captura.propuesta_anual != propuesta_anual
    captura.propuesta_anual = propuesta_anual
    captura.nota = nota
    captura.estado = "capturada" if propuesta_anual is not None else "pendiente"
    if cambio:
        # El importe anual ya no coincide con lo mensualizado antes: hay que volver a repartirlo,
        # a propósito no se adivina un nuevo reparto aquí.
        db.execute(
            delete(LineaPresupuestoMensual).where(
                LineaPresupuestoMensual.linea_captura_id == captura.id
            )
        )
        captura.perfil_distribucion_id = None
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.linea_capturada",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={
            "linea_id": linea_id,
            "propuesta_anual": str(propuesta_anual) if propuesta_anual is not None else None,
            "nota": nota,
        },
    )
    return captura


def fijar_objetivo(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    objetivo: Decimal | None,
    visibles: set[int] | None,
) -> LineaPresupuestoCaptura:
    """Fija el `objetivo` (referencia de Dirección) de una línea.

    No es una aprobación ni se mensualiza: a diferencia de `propuesta_anual`, cambiarlo no toca
    `estado` ni borra `LineaPresupuestoMensual`/`perfil_distribucion_id`.
    """
    ciclo = db.get(CicloPresupuesto, ciclo_id)
    if ciclo is None or ciclo.hotel_id != hotel_id:
        raise LookupError("Ciclo de presupuesto no encontrado")
    if visibles is not None and linea_id not in visibles:
        raise LookupError("Línea de captura no encontrada")
    captura = db.scalar(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo_id,
            LineaPresupuestoCaptura.linea_id == linea_id,
        )
    )
    if captura is None:
        raise LookupError("Línea de captura no encontrada")
    if ciclo.estado != "borrador":
        raise CapturaInvalida(409, "El ciclo no está en captura")
    captura.objetivo = objetivo
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.linea_objetivo",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id, "objetivo": str(objetivo) if objetivo is not None else None},
    )
    return captura


def _resumen_de(seccion: str | None, filas: list[LineaPresupuestoCaptura]) -> ResumenSeccion:
    total = len(filas)
    capturadas = sum(1 for f in filas if f.propuesta_anual is not None)
    cobertura = (
        (Decimal(capturadas) / Decimal(total) * 100).quantize(_PORCENTAJE)
        if total
        else Decimal("0.00")
    )
    suma_objetivo = sum((f.objetivo for f in filas if f.objetivo is not None), Decimal(0))
    suma_propuesta = sum(
        (f.propuesta_anual for f in filas if f.propuesta_anual is not None), Decimal(0)
    )
    return ResumenSeccion(
        seccion=seccion,
        total_lineas=total,
        lineas_capturadas=capturadas,
        cobertura_pct=cobertura,
        suma_objetivo=suma_objetivo,
        suma_propuesta=suma_propuesta,
    )


def resumen_ciclo(db: Session, *, ciclo: CicloPresupuesto) -> ResumenCiclo:
    """Cobertura y sumas de objetivo/propuesta del ciclo, total y por sección (diseño §6)."""
    if ciclo.version_estructura_id is None:
        raise CapturaInvalida(409, "El ciclo no tiene una estructura de reporte asociada")
    lineas = {
        x.id: x for x in RepositorioReporte(db, ciclo.hotel_id).lineas(ciclo.version_estructura_id)
    }
    nombres_seccion = {x.id: x.descripcion for x in lineas.values() if x.tipo == "seccion"}
    capturas = list(
        db.scalars(
            select(LineaPresupuestoCaptura).where(LineaPresupuestoCaptura.ciclo_id == ciclo.id)
        )
    )
    por_seccion: dict[str | None, list[LineaPresupuestoCaptura]] = {}
    for c in capturas:
        linea = lineas.get(c.linea_id)
        seccion = nombres_seccion.get(linea.seccion_id) if linea and linea.seccion_id else None
        por_seccion.setdefault(seccion, []).append(c)
    secciones = [
        _resumen_de(seccion, filas)
        for seccion, filas in sorted(por_seccion.items(), key=lambda kv: kv[0] or "")
    ]
    total = _resumen_de(None, capturas)
    return ResumenCiclo(
        total_lineas=total.total_lineas,
        lineas_capturadas=total.lineas_capturadas,
        cobertura_pct=total.cobertura_pct,
        suma_objetivo=total.suma_objetivo,
        suma_propuesta=total.suma_propuesta,
        por_seccion=secciones,
    )


def resumen_mensual_ciclo(db: Session, *, ciclo: CicloPresupuesto) -> ResumenMensualCiclo:
    """Suma de la propuesta mensualizada del ciclo por periodo (gráfica de distribución, diseño
    §4.2.B) y, además, por sección y periodo (mapa de calor, diseño §4.2.D). Es la propuesta **del
    ciclo en captura**, no el Budget vigente: solo cuenta lo que ya se mensualizó (por perfil o a
    mano); una línea con propuesta anual pero sin mensualizar todavía no aporta a ningún periodo y
    se cuenta aparte en `lineas_sin_mensualizar`.
    """
    capturas = list(
        db.scalars(
            select(LineaPresupuestoCaptura).where(
                LineaPresupuestoCaptura.ciclo_id == ciclo.id,
                LineaPresupuestoCaptura.propuesta_anual.is_not(None),
            )
        )
    )
    nombres_seccion: dict[int, str | None] = {}
    if ciclo.version_estructura_id is not None:
        lineas = {
            x.id: x for x in RepositorioReporte(db, ciclo.hotel_id).lineas(ciclo.version_estructura_id)
        }
        secciones = {x.id: x.descripcion for x in lineas.values() if x.tipo == "seccion"}
        for c in capturas:
            linea = lineas.get(c.linea_id)
            nombres_seccion[c.linea_id] = (
                secciones.get(linea.seccion_id) if linea and linea.seccion_id else None
            )

    sumas: dict[str, Decimal] = {}
    sumas_seccion: dict[tuple[str | None, str], Decimal] = {}
    mensualizadas = 0
    for c in capturas:
        meses = list(
            db.scalars(
                select(LineaPresupuestoMensual).where(
                    LineaPresupuestoMensual.linea_captura_id == c.id
                )
            )
        )
        if meses:
            mensualizadas += 1
        seccion = nombres_seccion.get(c.linea_id)
        for m in meses:
            sumas[m.periodo] = sumas.get(m.periodo, Decimal(0)) + m.importe
            clave = (seccion, m.periodo)
            sumas_seccion[clave] = sumas_seccion.get(clave, Decimal(0)) + m.importe
    por_periodo = [
        PuntoMensualCiclo(periodo=periodo, propuesta=importe)
        for periodo, importe in sorted(sumas.items())
    ]
    por_seccion_dict: dict[str | None, dict[str, Decimal]] = {}
    for (seccion, periodo), importe in sumas_seccion.items():
        por_seccion_dict.setdefault(seccion, {})[periodo] = importe
    por_seccion = [
        SeccionMensualCiclo(
            seccion=seccion,
            por_periodo=[
                PuntoMensualCiclo(periodo=periodo, propuesta=importe)
                for periodo, importe in sorted(periodos.items())
            ],
        )
        for seccion, periodos in sorted(por_seccion_dict.items(), key=lambda kv: kv[0] or "")
    ]
    return ResumenMensualCiclo(
        por_periodo=por_periodo,
        lineas_sin_mensualizar=len(capturas) - mensualizadas,
        por_seccion=por_seccion,
    )
