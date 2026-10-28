"""Tabla interna de una línea del Budget (p. ej. *Other Income*, Fase «Budget por cuenta», parte 1).

Cada mes de la línea se obtiene de una base y un factor (`importe = base × factor`, la base es el
Est-Act del año previo) o de un monto fijo. Guardar el detalle **es** mensualizar la línea: fija
`propuesta_anual` (la suma de los 12 meses) y los `LineaPresupuestoMensual`, así que aprobar el
ciclo (`presupuesto_ciclo._generar_version_plan`) no necesita saber que existe. Al aprobar, el
detalle se copia a `LineaPlanDetalle`, ligado a la `VersionPlan` (ADR 0003: una versión no se
edita).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.ingesta.budget_other_income import OtherIncomeLeido, normalizar
from fpa.modelos.plan import VersionPlan
from fpa.modelos.reporte import LineaReporte
from fpa.modelos.presupuesto import (
    METODOS_DETALLE,
    CicloPresupuesto,
    DetalleLineaPresupuesto,
    LineaPlanDetalle,
    LineaPresupuestoCaptura,
)
from fpa.modelos.tipos import MICRO
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.presupuesto_distribucion import (
    _reemplazar_lineas_mensuales,
    periodos_de_ano_fiscal,
)
from fpa.servicios.presupuesto_hoja import guardar_referencias_excel


class DetalleInvalido(Exception):
    """Detalle no válido o fuera de turno. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


@dataclass(frozen=True)
class CeldaDetalle:
    periodo: str
    metodo: str
    base: Decimal | None = None
    factor: Decimal | None = None
    monto_fijo: Decimal | None = None


@dataclass(frozen=True)
class DetalleCalculado:
    periodo: str
    metodo: str
    base: Decimal | None
    factor: Decimal | None
    monto_fijo: Decimal | None
    importe: Decimal


def calcular_importe(celda: CeldaDetalle) -> Decimal:
    """`factor`: `base × factor` a 6 decimales; `fijo`: el monto fijo. Falta un dato = 422."""
    if celda.metodo == "fijo":
        if celda.monto_fijo is None:
            raise DetalleInvalido(422, f"{celda.periodo}: falta el monto fijo")
        return celda.monto_fijo.quantize(MICRO)
    if celda.metodo == "factor":
        if celda.base is None or celda.factor is None:
            raise DetalleInvalido(422, f"{celda.periodo}: falta la base o el factor")
        return (celda.base * celda.factor).quantize(MICRO)
    raise DetalleInvalido(
        422, f"{celda.periodo}: el método debe ser uno de {', '.join(METODOS_DETALLE)}"
    )


def calcular_detalle(celdas: Sequence[CeldaDetalle]) -> list[DetalleCalculado]:
    return [
        DetalleCalculado(
            periodo=c.periodo,
            metodo=c.metodo,
            base=c.base,
            factor=c.factor,
            monto_fijo=c.monto_fijo,
            importe=calcular_importe(c),
        )
        for c in celdas
    ]


def _captura_de(
    db: Session, *, hotel_id: int, ciclo_id: int, linea_id: int, visibles: set[int] | None
) -> tuple[LineaPresupuestoCaptura, CicloPresupuesto]:
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
    return captura, ciclo


def leer_detalle(
    db: Session, *, hotel_id: int, ciclo_id: int, linea_id: int, visibles: set[int] | None
) -> list[DetalleLineaPresupuesto]:
    captura, _ = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    return list(
        db.scalars(
            select(DetalleLineaPresupuesto)
            .where(DetalleLineaPresupuesto.linea_captura_id == captura.id)
            .order_by(DetalleLineaPresupuesto.periodo)
        )
    )


def guardar_detalle(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    linea_id: int,
    celdas: Sequence[CeldaDetalle],
    visibles: set[int] | None,
    desde_partidas: bool = False,
) -> list[DetalleLineaPresupuesto]:
    """Reemplaza **completo** el detalle de la línea (no es parcial): exige los 12 periodos del año
    fiscal, calcula los importes y deja la línea mensualizada y con su propuesta anual."""
    captura, ciclo = _captura_de(
        db, hotel_id=hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    dados = [c.periodo for c in celdas]
    if len(dados) != len(set(dados)) or set(dados) != set(periodos):
        raise DetalleInvalido(
            422, "Hay que dar exactamente una celda para cada uno de los 12 periodos del año fiscal"
        )
    calculadas = {d.periodo: d for d in calcular_detalle(celdas)}
    importes = [calculadas[p].importe for p in periodos]
    anual = sum(importes, Decimal(0))
    # Mensualiza (y, de paso, borra el detalle anterior); después se guarda el nuevo.
    _reemplazar_lineas_mensuales(
        db,
        linea_captura_id=captura.id,
        periodos=periodos,
        importes=importes,
        desde_partidas=desde_partidas,
    )
    captura.propuesta_anual = anual
    captura.estado = "capturada"
    captura.perfil_distribucion_id = None
    filas = [
        DetalleLineaPresupuesto(
            linea_captura_id=captura.id,
            periodo=p,
            metodo=calculadas[p].metodo,
            base=calculadas[p].base,
            factor=calculadas[p].factor,
            monto_fijo=calculadas[p].monto_fijo,
            importe=calculadas[p].importe,
        )
        for p in periodos
    ]
    db.add_all(filas)
    db.flush()
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.detalle_guardado",
        entidad="linea_presupuesto_captura",
        entidad_id=captura.id,
        detalle={"linea_id": linea_id, "propuesta_anual": str(anual)},
    )
    return filas


def congelar_detalle(db: Session, *, ciclo: CicloPresupuesto, version: VersionPlan) -> int:
    """Copia el detalle de las líneas del ciclo a `LineaPlanDetalle`; devuelve cuántas filas."""
    filas = db.execute(
        select(LineaPresupuestoCaptura.linea_id, DetalleLineaPresupuesto)
        .join(
            DetalleLineaPresupuesto,
            DetalleLineaPresupuesto.linea_captura_id == LineaPresupuestoCaptura.id,
        )
        .where(LineaPresupuestoCaptura.ciclo_id == ciclo.id)
    ).all()
    for linea_id, d in filas:
        db.add(
            LineaPlanDetalle(
                version_plan_id=version.id,
                linea_id=linea_id,
                periodo=d.periodo,
                metodo=d.metodo,
                base=d.base,
                factor=d.factor,
                monto_fijo=d.monto_fijo,
                importe=d.importe,
            )
        )
    db.flush()
    return len(filas)


def leer_detalle_de_version(
    db: Session, *, hotel_id: int, version_plan_id: int, linea_id: int
) -> list[LineaPlanDetalle]:
    version = db.get(VersionPlan, version_plan_id)
    if version is None or version.hotel_id != hotel_id:
        raise LookupError("Versión de Budget no encontrada")
    return list(
        db.scalars(
            select(LineaPlanDetalle)
            .where(
                LineaPlanDetalle.version_plan_id == version_plan_id,
                LineaPlanDetalle.linea_id == linea_id,
            )
            .order_by(LineaPlanDetalle.periodo)
        )
    )


_SECCION_OTHER_INCOME = "otherincome"
_UMBRAL_PARECIDO = 0.6

# Secciones del Budget que se importan del Excel. Other Income se alinea por parecido de nombre; las
# demás, solo por nombre exacto (normalizado) o por el alias de abajo, para no caer en una línea
# equivocada (p. ej. «Insurance» en «Life Insurance»).
SECCION_MGMT_CHECKIN = "mgmtcheckin"

# Primero se busca la línea con el MISMO nombre (normalizado); si no hay, el alias: nombre del Excel
# (normalizado) -> nombre de la línea del reporte (normalizado). La estructura vigente del reporte de
# Mazatlán usa los mismos nombres que el Excel (salvo «Holydays» y «Miscellaneous Exp»); el resto de
# alias cubre la versión anterior del reporte.
ALIAS_MGMT_CHECKIN: dict[str, str] = {
    "holydays": "holidays",
    "sundaypremiums": "sundaypremium",
    "compensations": "compensation",
    "savingsfund": "savingfund",
    "incentive": "incentives",
    "transportationallow": "transportationallowance",
    "mileagetaxiparking": "mileagegasparking",
    "mealsentertain": "mealsentertainmentout",
    "postage": "postageexpressmail",
    "telocal": "localconsumes",  # «T & E Local»
    "insurance": "insurancefianzasyseguros",
    "miscellaneousexp": "miscellaneous",
    "materialssupplies": "materialssupplies",
}
ESTRICTAS = {SECCION_MGMT_CHECKIN: ALIAS_MGMT_CHECKIN}


@dataclass
class ResultadoImportacionDetalle:
    importadas: int = 0
    avisos: list[str] = field(default_factory=list)


def importar_other_income(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    leido: OtherIncomeLeido,
    visibles: set[int] | None,
) -> ResultadoImportacionDetalle:
    """Llena el detalle de la sección *Other Income* del ciclo (compatibilidad)."""
    return importar_seccion(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo_id=ciclo_id,
        leido=leido,
        visibles=visibles,
        seccion=_SECCION_OTHER_INCOME,
    )


def importar_seccion(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo_id: int,
    leido: OtherIncomeLeido,
    visibles: set[int] | None,
    seccion: str,
    linea_id: int | None = None,
) -> ResultadoImportacionDetalle:
    """Llena el detalle de las líneas de una sección del ciclo con lo leído del Excel.

    *Other Income*: cada cuenta cae en la línea de detalle que más se parece por nombre (mínimo 0.6,
    cada línea se usa una sola vez). Las demás secciones (`ESTRICTAS`): solo por nombre exacto o
    alias confirmado. Lo que no se pueda alinear se avisa.

    Con `linea_id` solo se traen las **partidas de esa cuenta** (su hoja de detalle del Excel): el
    resto de la sección no se toca.
    """
    ciclo = db.get(CicloPresupuesto, ciclo_id)
    if ciclo is None or ciclo.hotel_id != hotel_id:
        raise LookupError("Ciclo de presupuesto no encontrado")
    if ciclo.estado != "borrador":
        raise DetalleInvalido(409, "El ciclo no está en captura")
    if ciclo.version_estructura_id is None:
        raise DetalleInvalido(409, "El ciclo no tiene una estructura de reporte asociada")
    lineas = RepositorioReporte(db, hotel_id).lineas(ciclo.version_estructura_id)
    seccion_linea = next(
        (x for x in lineas if x.tipo == "seccion" and normalizar(x.descripcion) == seccion),
        None,
    )
    if seccion_linea is None:
        raise DetalleInvalido(
            409, f"La estructura del ciclo no tiene la sección «{_nombre_seccion(seccion)}»"
        )
    nombre = seccion_linea.descripcion
    candidatas = [x for x in lineas if x.tipo == "detalle" and x.seccion_id == seccion_linea.id]
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    res = ResultadoImportacionDetalle(avisos=list(leido.avisos))
    libres = {x.id: x for x in candidatas}
    alias = ESTRICTAS.get(seccion)
    if linea_id is not None:
        destino = next((x for x in candidatas if x.id == linea_id), None)
        if destino is None:
            raise DetalleInvalido(404, f"La cuenta no es de la sección «{nombre}»")
        res.avisos = []  # solo importa lo de esta cuenta, no los avisos del resto del libro
    con_partidas, importadas_partidas = _importar_partidas(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        ciclo=ciclo,
        candidatas=candidatas,
        leido=leido,
        visibles=visibles,
        periodos=periodos,
        res=res,
        solo_linea=linea_id,
    )
    res.importadas += importadas_partidas
    if linea_id is not None:
        if importadas_partidas == 0:
            res.avisos.append(
                f"«{destino.descripcion}» no tiene partidas en el Excel (su hoja de detalle falta "
                "o viene vacía); no se cambió nada"
            )
        else:
            _importar_referencias(db, ciclo_id, [destino], leido, alias, periodos)
        return res
    for con_id in con_partidas:
        libres.pop(con_id, None)
    _importar_referencias(db, ciclo_id, candidatas, leido, alias, periodos)
    for fila in leido.filas:
        mejor, mejor_valor = None, 0.0
        if alias is None:
            for linea in libres.values():
                v = SequenceMatcher(None, normalizar(fila.concepto), normalizar(linea.descripcion))
                if v.ratio() > mejor_valor:
                    mejor, mejor_valor = linea, v.ratio()
            if mejor is not None and mejor_valor < _UMBRAL_PARECIDO:
                mejor = None
        else:
            objetivos = [normalizar(fila.concepto)]
            if normalizar(fila.concepto) in alias:
                objetivos.append(alias[normalizar(fila.concepto)])
            mejor = next(
                (
                    x
                    for objetivo in objetivos
                    for x in libres.values()
                    if normalizar(x.descripcion) == objetivo
                ),
                None,
            )
        if mejor is None:
            res.avisos.append(f"«{fila.concepto}» no tiene línea en {nombre}; se ignora")
            continue
        del libres[mejor.id]
        if visibles is not None and mejor.id not in visibles:
            res.avisos.append(f"«{fila.concepto}» está fuera de tu alcance; se omite")
            continue
        if _usa_partidas(db, ciclo_id, mejor.id):
            res.avisos.append(f"«{fila.concepto}» se captura por partidas; no se toca su importe")
            continue
        guardar_detalle(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            ciclo_id=ciclo_id,
            linea_id=mejor.id,
            celdas=[
                CeldaDetalle(
                    periodo=p,
                    metodo=c.metodo,
                    base=c.base,
                    factor=c.factor,
                    monto_fijo=c.monto_fijo,
                )
                for p, c in zip(periodos, fila.celdas, strict=True)
            ],
            visibles=visibles,
        )
        res.importadas += 1
    if guardar_referencias_excel(db, ciclo=ciclo, seccion_id=seccion_linea.id, leido=leido):
        res.avisos.append(
            "Se guardaron la inflación mensual, el Est Act y el Budget del año previo del Excel"
        )
    # Las que el archivo trae con #REF! ya se avisaron; aquí solo las que NO venían en el archivo
    avisadas = {normalizar(c) for c in leido.sin_importes}
    avisadas |= {alias[c] for c in avisadas if alias and c in alias}
    ausentes = [x for x in libres.values() if normalizar(x.descripcion) not in avisadas]
    if ausentes:
        res.avisos.append(
            f"{len(ausentes)} líneas de {nombre} no venían en el archivo y quedan para captura: "
            + ", ".join(f"«{x.descripcion}»" for x in ausentes)
        )
    return res


def _usa_partidas(db: Session, ciclo_id: int, linea_id: int) -> bool:
    captura = db.scalar(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo_id,
            LineaPresupuestoCaptura.linea_id == linea_id,
        )
    )
    return bool(captura is not None and captura.usa_partidas)


def _linea_de_hoja(candidatas: Sequence[LineaReporte], dep: str, cuenta: str, nombre: str):  # type: ignore[no-untyped-def]
    """La línea de una hoja de detalle: mismo número de cuenta y nombre (el título de la hoja viene
    cortado a 31 letras, así que también vale que el nombre de la línea empiece igual)."""
    objetivo = normalizar(nombre)
    mismas = [
        x for x in candidatas if f"-{dep}-{cuenta}-" in (x.codigo_corporativo or "")
    ]
    exacta = next((x for x in mismas if normalizar(x.descripcion) == objetivo), None)
    if exacta is not None:
        return exacta
    return next(
        (
            x
            for x in mismas
            if normalizar(x.descripcion).startswith(objetivo)
            or objetivo.startswith(normalizar(x.descripcion))
        ),
        None,
    )


def _importar_partidas(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    ciclo: CicloPresupuesto,
    candidatas: Sequence[LineaReporte],
    leido: OtherIncomeLeido,
    visibles: set[int] | None,
    periodos: Sequence[str],
    res: ResultadoImportacionDetalle,
    solo_linea: int | None = None,
) -> tuple[set[int], int]:
    """Importa las hojas de detalle (partidas) como cuentas por partidas; devuelve (líneas
    atendidas, cuántas se importaron). El Budget de esas cuentas sale de las partidas × inflación.
    Con `solo_linea` se atiende únicamente la hoja de esa cuenta."""
    from fpa.servicios.presupuesto_partidas import (  # noqa: PLC0415 (evita el ciclo de imports)
        PartidaEntrada,
        budget_mensual,
        calcular_partida,
        distribucion_de,
        guardar_partidas,
    )

    atendidas: set[int] = set()
    importadas = 0
    for hoja in leido.partidas:
        if solo_linea is not None:
            de_esta = _linea_de_hoja(candidatas, hoja.departamento, hoja.cuenta, hoja.nombre)
            if de_esta is None or de_esta.id != solo_linea:
                continue
        res.avisos.extend(hoja.avisos)
        if not hoja.partidas:
            continue
        linea = _linea_de_hoja(candidatas, hoja.departamento, hoja.cuenta, hoja.nombre)
        if linea is None:
            res.avisos.append(f"«{hoja.hoja}» no tiene línea en el reporte; se ignora")
            continue
        atendidas.add(linea.id)
        if visibles is not None and linea.id not in visibles:
            res.avisos.append(f"«{linea.descripcion}» está fuera de tu alcance; se omite")
            continue
        entradas = [
            PartidaEntrada(
                p.concepto, p.cantidad, p.unidad, p.costo, p.metodo,
                None if p.metodo == "mensual" else p.meses,
            )
            for p in hoja.partidas
        ]  # fmt: skip
        tasas = dict(zip(periodos, hoja.inflacion, strict=True))
        guardar_partidas(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            ciclo_id=ciclo.id,
            linea_id=linea.id,
            partidas=entradas,
            inflacion=tasas,
            visibles=visibles,
        )
        importadas += 1
        # ¿cuadra con lo que dice la hoja principal del Budget?
        calculadas = [calcular_partida(e, i) for i, e in enumerate(entradas, start=1)]
        mio = budget_mensual(distribucion_de(calculadas), hoja.inflacion)
        fila = next(
            (f for f in leido.filas if normalizar(f.concepto) == normalizar(linea.descripcion)), None
        )
        if fila is not None and any(
            abs(c.importe - m) > Decimal("0.01") for c, m in zip(fila.celdas, mio, strict=True)
        ):
            res.avisos.append(
                f"«{linea.descripcion}»: las partidas dan {sum(mio, Decimal(0)):,.2f} y la hoja Budget "
                f"{fila.total:,.2f}; se importan las partidas"
            )
        for c in calculadas:
            if c.diferencia != 0:
                res.avisos.append(
                    f"«{linea.descripcion}» «{c.concepto[:30]}»: sus meses suman {c.suma:,.2f} y su "
                    f"costo extendido es {c.extendido:,.2f}"
                )
    return atendidas, importadas


def _importar_referencias(
    db: Session,
    ciclo_id: int,
    candidatas: Sequence[LineaReporte],
    leido: OtherIncomeLeido,
    alias: dict[str, str] | None,
    periodos: Sequence[str],
) -> None:
    """Est-Act y Budget del año previo por cuenta (de las hojas del año previo, por nombre)."""
    if not leido.referencias:
        return
    from fpa.servicios.presupuesto_partidas import guardar_referencias_cuenta  # noqa: PLC0415

    # nombre de la línea del reporte (normalizado) por cada nombre normalizado del Excel
    inverso = {v: k for k, v in (alias or {}).items()}
    for linea in candidatas:
        nombre = normalizar(linea.descripcion)
        ref = leido.referencias.get(nombre) or leido.referencias.get(inverso.get(nombre, ""))
        if ref is None:
            continue
        captura = db.scalar(
            select(LineaPresupuestoCaptura).where(
                LineaPresupuestoCaptura.ciclo_id == ciclo_id,
                LineaPresupuestoCaptura.linea_id == linea.id,
            )
        )
        if captura is not None:
            guardar_referencias_cuenta(
                db, captura_id=captura.id, periodos=periodos, est_act=ref[0], budget_previo=ref[1]
            )


def _nombre_seccion(seccion: str) -> str:
    return {"otherincome": "Other Income", SECCION_MGMT_CHECKIN: "Mgmt & Check In"}.get(
        seccion, seccion
    )
