"""Partidas de una cuenta del Budget (p. ej. *Other Fringe* de Mgmt & Check In).

Una cuenta con partidas se captura como en las hojas de detalle del Excel:

- cada **partida** tiene cantidad, unidad y costo; su **costo extendido = cantidad × costo**;
- se **reparte** por mes: `mensual` (el extendido entre 12; el residuo de micros va a los primeros meses
  para que la suma cierre exacto), `estacional` (meses capturados) o `importada` (meses del Excel);
- la **distribución** del mes es la suma de las partidas y el **Budget del mes = distribución × (1 +
  inflación del mes)**: la inflación SÍ entra al Budget (igual que en el Excel).

Guardar las partidas es mensualizar la cuenta: el Budget calculado se escribe como detalle `fijo`
(`guardar_detalle`), así que la hoja de sección, la comparación anual, Variance y la generación del plan
leen lo mismo que con cualquier otra cuenta. La edición mes a mes (Editor mensual) queda bloqueada
mientras la cuenta use partidas (ver `_reemplazar_lineas_mensuales`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fpa.modelos.presupuesto import (
    METODOS_PARTIDA,
    InflacionLineaMes,
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
    PartidaLinea,
    PartidaMes,
    ReferenciaLineaMes,
)
from fpa.modelos.tipos import MICRO
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.presupuesto_detalle import CeldaDetalle, DetalleInvalido, _captura_de, guardar_detalle
from fpa.servicios.presupuesto_distribucion import periodos_de_ano_fiscal
from fpa.servicios.presupuesto_hoja import BloqueInferior, calcular_bloque

_CERO = Decimal(0)
MAX_PARTIDAS = 200
MAX_IMPORTE = Decimal("1000000000000")  # 1 billón: tope de cordura, no de negocio


@dataclass(frozen=True)
class PartidaEntrada:
    concepto: str
    cantidad: Decimal
    unidad: str | None
    costo: Decimal
    metodo: str
    meses: Sequence[Decimal] | None = None  # 12 importes, solo `estacional` e `importada`


@dataclass(frozen=True)
class PartidaCalculada:
    id: int | None
    orden: int
    concepto: str
    cantidad: Decimal
    unidad: str | None
    costo: Decimal
    metodo: str
    extendido: Decimal
    meses: list[Decimal]
    suma: Decimal
    diferencia: Decimal  # suma de meses − costo extendido (0 = cuadra)


def costo_extendido(cantidad: Decimal, costo: Decimal) -> Decimal:
    return (cantidad * costo).quantize(MICRO)


def repartir_mensual(extendido: Decimal, n: int = 12) -> list[Decimal]:
    """El extendido entre `n` meses; el residuo (en micros) va a los primeros meses: la suma cierra."""
    base = (extendido / n).quantize(MICRO, rounding=ROUND_DOWN)
    resto = int((extendido - base * n) / MICRO)
    return [base + (MICRO if i < resto else _CERO) for i in range(n)]


def validar_entradas(entradas: Sequence[PartidaEntrada]) -> None:
    if not entradas:
        raise DetalleInvalido(422, "La cuenta necesita al menos una partida")
    if len(entradas) > MAX_PARTIDAS:
        raise DetalleInvalido(422, f"Una cuenta admite hasta {MAX_PARTIDAS} partidas")
    for i, e in enumerate(entradas, start=1):
        nombre = f"Partida {i}"
        if not e.concepto.strip() or len(e.concepto.strip()) > 120:
            raise DetalleInvalido(422, f"{nombre}: el concepto va de 1 a 120 caracteres")
        if e.unidad is not None and len(e.unidad.strip()) > 20:
            raise DetalleInvalido(422, f"{nombre}: la unidad admite hasta 20 caracteres")
        if e.metodo not in METODOS_PARTIDA:
            raise DetalleInvalido(
                422, f"{nombre}: la distribución debe ser una de {', '.join(METODOS_PARTIDA)}"
            )
        if e.cantidad < 0 or e.costo < 0 or e.cantidad > MAX_IMPORTE or e.costo > MAX_IMPORTE:
            raise DetalleInvalido(422, f"{nombre}: la cantidad y el costo no pueden ser negativos")
        if e.metodo != "mensual":
            if e.meses is None or len(e.meses) != 12:
                raise DetalleInvalido(422, f"{nombre}: faltan los 12 meses de la distribución")
            if any(m < 0 or m > MAX_IMPORTE for m in e.meses):
                raise DetalleInvalido(422, f"{nombre}: un mes no puede ser negativo")


def calcular_partida(e: PartidaEntrada, orden: int, id_: int | None = None) -> PartidaCalculada:
    extendido = costo_extendido(e.cantidad, e.costo)
    meses = (
        repartir_mensual(extendido)
        if e.metodo == "mensual"
        else [m.quantize(MICRO) for m in (e.meses or [])]
    )
    suma = sum(meses, _CERO)
    return PartidaCalculada(
        id=id_,
        orden=orden,
        concepto=e.concepto.strip(),
        cantidad=e.cantidad,
        unidad=(e.unidad or "").strip() or None,
        costo=e.costo,
        metodo=e.metodo,
        extendido=extendido,
        meses=meses,
        suma=suma,
        diferencia=suma - extendido,
    )


def distribucion_de(partidas: Sequence[PartidaCalculada]) -> list[Decimal]:
    """Suma de las partidas, mes a mes (sin inflación)."""
    return [sum((p.meses[i] for p in partidas), _CERO) for i in range(12)]


def budget_mensual(distribucion: Sequence[Decimal], tasas: Sequence[Decimal | None]) -> list[Decimal]:
    """Budget del mes = distribución × (1 + inflación del mes)."""
    return calcular_bloque(distribucion, tasas, [None] * 12, [None] * 12).total_con_inflacion


def _tasas_en_orden(periodos: Sequence[str], tasas: dict[str, Decimal]) -> list[Decimal]:
    if set(tasas) != set(periodos):
        raise DetalleInvalido(422, "Hay que dar la inflación de cada uno de los 12 periodos")
    if any(t < -1 or t > 1 for t in tasas.values()):
        raise DetalleInvalido(422, "La inflación mensual debe estar entre -100 % y 100 %")
    return [tasas[p].quantize(MICRO) for p in periodos]


def guardar_partidas(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    partidas: Sequence[PartidaEntrada],
    inflacion: dict[str, Decimal],
    visibles: set[int] | None,
) -> list[PartidaCalculada]:
    """Reemplaza **completas** las partidas y la inflación de la cuenta (no es parcial) y deja la
    cuenta mensualizada con su Budget (distribución × (1 + inflación))."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    validar_entradas(partidas)
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    tasas = _tasas_en_orden(periodos, inflacion)
    calculadas = [calcular_partida(e, i) for i, e in enumerate(partidas, start=1)]
    budget = budget_mensual(distribucion_de(calculadas), tasas)
    # El Budget calculado mensualiza la línea (y revisa que no haya otro camino que la edite)
    guardar_detalle(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        linea_id=linea_id,
        celdas=[
            CeldaDetalle(periodo=p, metodo="fijo", monto_fijo=b)
            for p, b in zip(periodos, budget, strict=True)
        ],
        visibles=visibles,
        desde_partidas=True,
    )
    _borrar_partidas(db, captura.id)
    guardadas: list[PartidaCalculada] = []
    for c in calculadas:
        fila = PartidaLinea(
            linea_captura_id=captura.id,
            orden=c.orden,
            concepto=c.concepto,
            cantidad=c.cantidad,
            unidad=c.unidad,
            costo=c.costo,
            metodo=c.metodo,
        )
        db.add(fila)
        db.flush()
        if c.metodo != "mensual":
            db.add_all(
                PartidaMes(partida_id=fila.id, periodo=p, importe=m)
                for p, m in zip(periodos, c.meses, strict=True)
            )
        guardadas.append(
            PartidaCalculada(
                fila.id, c.orden, c.concepto, c.cantidad, c.unidad, c.costo, c.metodo,
                c.extendido, c.meses, c.suma, c.diferencia,
            )  # fmt: skip
        )
    db.add_all(
        InflacionLineaMes(linea_captura_id=captura.id, periodo=p, tasa=t)
        for p, t in zip(periodos, tasas, strict=True)
    )
    captura.usa_partidas = True
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.partidas_guardadas",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={
            "linea_id": linea_id,
            "partidas": len(guardadas),
            "propuesta_anual": str(captura.propuesta_anual),
            "sin_cuadrar": [g.concepto for g in guardadas if g.diferencia != 0],
        },
    )
    return guardadas


def _borrar_partidas(db: Session, captura_id: int) -> None:
    ids = list(
        db.scalars(select(PartidaLinea.id).where(PartidaLinea.linea_captura_id == captura_id))
    )
    if ids:
        db.execute(delete(PartidaMes).where(PartidaMes.partida_id.in_(ids)))
    db.execute(delete(PartidaLinea).where(PartidaLinea.linea_captura_id == captura_id))
    db.execute(delete(InflacionLineaMes).where(InflacionLineaMes.linea_captura_id == captura_id))
    db.flush()


@dataclass
class HojaCuenta:
    linea_id: int
    cuenta: str
    codigo: str | None
    seccion_id: int | None
    seccion: str
    periodos: list[str]
    partidas: list[PartidaCalculada]
    totales: list[Decimal]  # distribución (sin inflación)
    inflacion: list[Decimal | None]
    est_act: list[Decimal | None]
    budget_previo: list[Decimal | None]
    origen: str | None
    bloque: BloqueInferior = field(default=None)  # type: ignore[assignment]


def _partidas_guardadas(
    db: Session, captura_id: int, periodos: Sequence[str]
) -> list[PartidaCalculada]:
    filas = list(
        db.scalars(
            select(PartidaLinea)
            .where(PartidaLinea.linea_captura_id == captura_id)
            .order_by(PartidaLinea.orden, PartidaLinea.id)
        )
    )
    salida: list[PartidaCalculada] = []
    for f in filas:
        guardados = {
            m.periodo: m.importe
            for m in db.scalars(select(PartidaMes).where(PartidaMes.partida_id == f.id))
        }
        entrada = PartidaEntrada(
            concepto=f.concepto,
            cantidad=f.cantidad,
            unidad=f.unidad,
            costo=f.costo,
            metodo=f.metodo,
            meses=None if f.metodo == "mensual" else [guardados.get(p, _CERO) for p in periodos],
        )
        salida.append(calcular_partida(entrada, f.orden, f.id))
    return salida


def leer_hoja_de_cuenta(
    db: Session, *, hotel_id: int, ciclo_id: int, linea_id: int, visibles: set[int] | None
) -> HojaCuenta:
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if not captura.usa_partidas:
        raise DetalleInvalido(409, "La cuenta no se captura por partidas")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    partidas = _partidas_guardadas(db, captura.id, periodos)
    tasas = {
        t.periodo: t.tasa
        for t in db.scalars(
            select(InflacionLineaMes).where(InflacionLineaMes.linea_captura_id == captura.id)
        )
    }
    refs = {
        r.periodo: r
        for r in db.scalars(
            select(ReferenciaLineaMes).where(ReferenciaLineaMes.linea_captura_id == captura.id)
        )
    }
    inflacion = [tasas.get(p) for p in periodos]
    est_act = [refs[p].est_act if p in refs else None for p in periodos]
    previo = [refs[p].budget_previo if p in refs else None for p in periodos]
    totales = distribucion_de(partidas)
    lineas = RepositorioReporte(db, hotel_id).lineas(ciclo.version_estructura_id or 0)
    linea = next((x for x in lineas if x.id == linea_id), None)
    seccion = next((x for x in lineas if linea and x.id == linea.seccion_id), None)
    return HojaCuenta(
        linea_id=linea_id,
        cuenta=linea.descripcion if linea else "",
        codigo=linea.codigo_corporativo if linea else None,
        seccion_id=seccion.id if seccion else None,
        seccion=seccion.descripcion if seccion else "",
        periodos=periodos,
        partidas=partidas,
        totales=totales,
        inflacion=inflacion,
        est_act=est_act,
        budget_previo=previo,
        origen=next((r.origen for r in refs.values()), None),
        bloque=calcular_bloque(totales, inflacion, est_act, previo),
    )


def guardar_inflacion_cuenta(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    inflacion: dict[str, Decimal],
    visibles: set[int] | None,
) -> None:
    """Cambia solo la inflación (12 meses) conservando las partidas; recalcula el Budget."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if not captura.usa_partidas:
        raise DetalleInvalido(409, "La cuenta no se captura por partidas")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    entradas = [
        PartidaEntrada(p.concepto, p.cantidad, p.unidad, p.costo, p.metodo,
                       None if p.metodo == "mensual" else p.meses)
        for p in _partidas_guardadas(db, captura.id, periodos)
    ]  # fmt: skip
    guardar_partidas(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        linea_id=linea_id,
        partidas=entradas,
        inflacion=inflacion,
        visibles=visibles,
    )


def activar_partidas(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    visibles: set[int] | None,
) -> None:
    """Pasa la cuenta a partidas. Si ya tenía importes mensuales, se conservan como una partida
    «Importe actual» (estacional) para no perder cifras; si no, queda lista para agregar partidas."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    if captura.usa_partidas:
        return
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    actuales = {
        m.periodo: m.importe
        for m in db.scalars(
            select(LineaPresupuestoMensual).where(
                LineaPresupuestoMensual.linea_captura_id == captura.id
            )
        )
    }
    meses = [actuales.get(p, _CERO) for p in periodos]
    if any(m != 0 for m in meses):
        guardar_partidas(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            partidas=[
                PartidaEntrada(
                    "Importe actual", Decimal(1), None, sum(meses, _CERO), "estacional", meses
                )
            ],
            inflacion={p: _CERO for p in periodos},
            visibles=visibles,
        )
        return
    captura.usa_partidas = True
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.partidas_activadas",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id},
    )


def quitar_partidas(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    visibles: set[int] | None,
) -> None:
    """Vuelve la cuenta al Editor mensual: las partidas se borran y el Budget que ya tenía queda
    como detalle `fijo` (sin perder cifras)."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    _borrar_partidas(db, captura.id)
    captura.usa_partidas = False
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.partidas_quitadas",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id},
    )


def guardar_referencias_cuenta(
    db: Session,
    *,
    captura_id: int,
    periodos: Sequence[str],
    est_act: Sequence[Decimal | None] | None,
    budget_previo: Sequence[Decimal | None] | None,
) -> None:
    """Est-Act y Budget del año previo de una cuenta (12 meses; lo que no venga queda como estaba)."""
    if est_act is None and budget_previo is None:
        return
    existentes = {
        r.periodo: r
        for r in db.scalars(
            select(ReferenciaLineaMes).where(ReferenciaLineaMes.linea_captura_id == captura_id)
        )
    }
    for i, p in enumerate(periodos):
        fila = existentes.get(p)
        if fila is None:
            fila = ReferenciaLineaMes(linea_captura_id=captura_id, periodo=p)
            db.add(fila)
        if est_act is not None:
            fila.est_act = est_act[i]
        if budget_previo is not None:
            fila.budget_previo = budget_previo[i]
        fila.origen = "excel"
    db.flush()
