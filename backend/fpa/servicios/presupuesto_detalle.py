"""Tabla interna de una línea del Budget (p. ej. *Other Income*, Fase «Budget por cuenta», parte 1).

Cada mes de la línea se obtiene de una base y un factor (`importe = base × factor`, la base es el
Est-Act del año previo) o de un monto fijo. Guardar el detalle **es** mensualizar la línea: fija
`propuesta_anual` (la suma de los 12 meses) y los `LineaPresupuestoMensual`, así que aprobar el
ciclo (`presupuesto_ciclo._generar_version_plan`) no necesita saber que existe. Al aprobar, el
detalle se copia a `LineaPlanDetalle`, ligado a la `VersionPlan` (ADR 0003: una versión no se
edita).
"""

from __future__ import annotations

import re
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
SECCION_ACCOUNTING = "accounting"

# Accounting (depto 0115): el Excel escribe «Non Deductable» y el reporte «Non-Deductible» (misma cuenta
# 61790); las hojas de detalle traen «Contrac Serv Other» (cuenta 60455, que comparte con «Computer
# Services», por eso no se empareja solo por código). Alias confirmados por nombre, no por parecido.
ALIAS_ACCOUNTING: dict[str, str] = {
    "nondeductable": "nondeductible",
    "contracservother": "contractservother",
}
SECCION_MAID_LINEN = "maidlinen"

# Maid & Linen (depto 0114): el Excel escribe en plural / con «Exp» algunas cuentas de nómina y
# «Non Deductable» (cuenta 61790, también en su hoja de detalle) donde el reporte dice «Non-Deductible».
ALIAS_MAID_LINEN: dict[str, str] = {
    "compensations": "compensation",
    "incentives": "incentive",
    "mealallowances": "mealallowance",
    "miscellaneousexp": "miscellaneous",
    "nondeductable": "nondeductible",
}
SECCION_APARTMENT_INTERIOR = "apartmentinterior"

# Apartment Interior (depto 0118). Las líneas «PH» son cuentas aparte de las normales. La línea sin PH
# del reporte se llama «Equipment/Supplies» (el Excel la escribe «Equip/Supplies» y su hoja
# «Equip-Supplies»); la hoja del Kit PH trae el nombre cortado («Kit Item-Rplcm PH»).
ALIAS_APARTMENT_INTERIOR: dict[str, str] = {
    "mealallowances": "mealallowance",
    "nondeductable": "nondeductible",
    "equipsupplies": "equipmentsupplies",
    "kititemrplcmph": "kititemsrplcmntph",
}
SECCION_COMMON_AREA = "commonarea"
SECCION_UTILITIES = "utilities"
SECCION_OWNER_ACTIVITIES = "owneractivities"
SECCION_OTHER_TAXES = "othertaxesfeesandinsurance"
SECCION_OWNER_SERVICES = "ownerservices"
SECCION_PURCHASING = "purchasing"

# Commercial Services. Cada negocio tiene dos secciones con el mismo nombre (`store`, `store#2`); los alias son
# por negocio y valen para sus dos secciones. Alias confirmados nombre a nombre, nunca por parecido.
ALIAS_TRAVEL_AGENCY: dict[str, str] = {
    "bankcommisions": "bankcommissions",  # el Excel y su hoja escriben mal «Commissions»
    "miscellaneousnoded": "miscellaneousnondeductibles",  # título de su hoja de detalle
}
ALIAS_STORE: dict[str, str] = {"nondeductable": "nondeductible"}
ALIAS_RESTAURANT: dict[str, str] = {"nondeductable": "nondeductible"}
# Departamentos que comparten hojas con otras secciones (una hoja de otra sección se omite en silencio)
DEPARTAMENTOS_COMPARTIDOS = {"0000", "0120", "0128", "0103", "0124", "0109", "5036"}
# Hojas cuya cuenta (o departamento) no es el de su línea en el reporte: la de Promotion de Restaurant trae la
# 60160 y el reporte la 60170; la de Telephone de IT Systems se llama `0000-60560` y su línea es `1136-61560`
CUENTA_DE_HOJA_EQUIVALENTE: dict[tuple[str, str], str | tuple[str, str]] = {
    ("0124", "60160"): "60170",
    ("0000", "60560"): ("1136", "61560"),
}

# Legal (depto 0130) e IT Systems (depto 1136; sus hojas vienen abreviadas y cortadas a 31 letras)
ALIAS_LEGAL: dict[str, str] = {
    "vacations": "vacation",
    "compensations": "compensation",
    "miscellaneousexp": "miscellaneous",
    "nondeductexp": "nondeductible",
}
ALIAS_IT_SYSTEMS: dict[str, str] = {
    "vacations": "vacation",
    "compensations": "compensation",
    "mealsenterntnear": "mealsentertain",
    "mealsenterntn": "mealsentertain",  # título de la hoja, cortado
    "nondeductexpenses": "nondeductible",
    "repmaintequip": "repairsmaintenanceequipment",
    "repmaintdsof": "repairsmaintdesktopsoftware",
    "repmaintdha": "repairsmaintdesktophardware",
    "repmaintnsof": "repairsmaintnetworksoftware",
    "repmaintnhar": "repairsmaintnetworkhardware",
    "repmaintphone": "repairsmaintphonesystem",
}

# Purchasing (depto 0122): Airfare, Lodging y Meals comparten la cuenta 61630 (se distinguen por nombre); el
# Excel y la hoja escriben distinto «Meals», «Mileage Parking», «Non Deductable» y (sin importes) «Compensations».
ALIAS_PURCHASING: dict[str, str] = {
    "compensations": "compensation",
    "meals": "mealsentertain",
    "mileageparking": "mileagetaxiparking",
    "nondeductable": "nondeductible",
}
# VDS Allocation Collections: dos líneas (cobranza en pesos negativa y su IVA) que el Excel trae en la hoja
# principal; su hoja de detalle (USD × tipo de cambio − IVA) no es de partidas y no se lee.
SECCION_VDS = "vdsallocationcollections"

# Owner Services (depto 0108): el Excel y sus hojas de detalle escriben distinto (plurales, faltas de ortografía,
# títulos cortados a 31 letras) varias cuentas del reporte. Alias confirmados nombre a nombre, nunca por parecido.
ALIAS_OWNER_SERVICES: dict[str, str] = {
    "vacations": "vacation",
    "vacationsbonus": "vacationbonus",
    "incentives": "incentive",
    "telephonefax": "telephone",
    "mealsentern": "mealsentertain",
    "milleagetaxisparking": "mileagetaxiparking",
    "milleagetaxispar": "mileagetaxiparking",  # título de la hoja de detalle, cortado
    "localcomsumos": "localconsumes",
    "localconsumos": "localconsumes",  # título de la hoja de detalle
    "miscexpense": "miscellaneous",
    "nondeductexp": "nondeductible",
}

# Other Taxes, Fees and Insurance (depto 0000, compartido): el Excel escribe distinto tres cuentas sin
# importes («Non- Deductble», «Seniority Premium Acrued» y «Adm Fee 4%» donde el reporte dice «Adm Fee 6%»).
ALIAS_OTHER_TAXES: dict[str, str] = {
    "nondeductble": "nondeductible",
    "senioritypremiumacrued": "senioritypremium",
    "admfee4": "admfee6",
}

# Owner Activities (depto 0101): el Excel escribe «Compensations» donde el reporte dice «Compensation»
# (nómina sin importes); sus cinco hojas de detalle emparejan por nombre.
ALIAS_OWNER_ACTIVITIES: dict[str, str] = {"compensations": "compensation"}

# Common Area (depto 0106): solo difieren dos cuentas de nómina sin importes («Savings Bonus» y
# «Meal Allowances») y las hojas de detalle emparejan por nombre (títulos cortados a 31 letras).
ALIAS_COMMON_AREA: dict[str, str] = {
    "savingsbonus": "savingsfund",
    "mealallowances": "mealallowance",
}
ESTRICTAS = {
    SECCION_MGMT_CHECKIN: ALIAS_MGMT_CHECKIN,
    SECCION_ACCOUNTING: ALIAS_ACCOUNTING,
    SECCION_MAID_LINEN: ALIAS_MAID_LINEN,
    SECCION_APARTMENT_INTERIOR: ALIAS_APARTMENT_INTERIOR,
    SECCION_COMMON_AREA: ALIAS_COMMON_AREA,
    SECCION_OWNER_ACTIVITIES: ALIAS_OWNER_ACTIVITIES,
    SECCION_OTHER_TAXES: ALIAS_OTHER_TAXES,
    SECCION_OWNER_SERVICES: ALIAS_OWNER_SERVICES,
    SECCION_PURCHASING: ALIAS_PURCHASING,
    "telephones": {},
    "travelagency": ALIAS_TRAVEL_AGENCY,
    "store": ALIAS_STORE,
    "cafeteria": {},
    "bar": {},
    "moneyexchange": {"incentives": "incentive"},  # el Excel escribe «Incentives»
    "restaurant": ALIAS_RESTAURANT,
    "legal": ALIAS_LEGAL,
    "itsystems": ALIAS_IT_SYSTEMS,
    SECCION_VDS: {},  # sus dos líneas se llaman igual en el Excel y en el reporte
    SECCION_UTILITIES: {},  # sus cuentas se llaman igual en el Excel y en el reporte
}


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
    clave, ordinal = seccion, 1
    if "#" in seccion:
        clave, _, n = seccion.partition("#")
        ordinal = int(n) if n.isdigit() else 1
    mismas = sorted(
        (x for x in lineas if x.tipo == "seccion" and normalizar(x.descripcion) == clave),
        key=lambda x: x.orden,
    )
    seccion_linea = mismas[ordinal - 1] if len(mismas) >= ordinal else None
    if seccion_linea is None:
        raise DetalleInvalido(
            409, f"La estructura del ciclo no tiene la sección «{_nombre_seccion(clave)}»"
        )
    seccion = clave
    nombre = seccion_linea.descripcion
    candidatas = [x for x in lineas if x.tipo == "detalle" and x.seccion_id == seccion_linea.id]
    periodos = periodos_de_ano_fiscal(db, ciclo.ano_fiscal_id)
    res = ResultadoImportacionDetalle(avisos=_avisos_de_la_seccion(leido.avisos, candidatas))
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
        alias=alias,
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
    por_partidas = [x for con_id in con_partidas if (x := libres.get(con_id)) is not None]
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
            if mejor is None and any(
                normalizar(x.descripcion) in objetivos for x in por_partidas
            ):
                # La cuenta ya se importó por sus partidas (su Budget sale de ellas × inflación):
                # la fila del Budget resumido no se importa ni se avisa como si faltara la línea.
                continue
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
    return bool(captura is not None and (captura.usa_partidas or captura.usa_consumo))


def _cuadra_con_su_total(hoja) -> tuple[bool, Decimal, Decimal | None]:  # type: ignore[no-untyped-def]
    """¿Las partidas de la hoja suman su Total Expense? Se revisan la suma de cantidad × costo y la de los
    meses (tolerancia: 1 peso o 1 %). Una hoja de cálculo (IVA, Income Tax) o un calendario (Depreciation)
    no cuadra y no debe importarse por partidas. Sin Total Expense no hay con qué comparar."""
    suma_extendida = sum((p.cantidad * p.costo for p in hoja.partidas), Decimal(0))
    suma_meses = sum((m for p in hoja.partidas for m in p.meses), Decimal(0))
    total = hoja.total_expense
    if total is None:
        return True, suma_extendida, None
    margen = max(Decimal(1), abs(total) * Decimal("0.01"))
    return abs(suma_extendida - total) <= margen and abs(suma_meses - total) <= margen, suma_extendida, total


def _destino_de_hoja(dep: str, cuenta: str) -> tuple[str, str]:
    """(departamento, cuenta) de la línea a la que pertenece una hoja (casi siempre los suyos)."""
    destino = CUENTA_DE_HOJA_EQUIVALENTE.get((dep, cuenta))
    if destino is None:
        return dep, cuenta
    return destino if isinstance(destino, tuple) else (dep, destino)


def _avisos_de_la_seccion(avisos: Sequence[str], candidatas: Sequence[LineaReporte]) -> list[str]:
    """Los avisos de la lectura, sin los de hojas del departamento compartido `0000` que son de otra
    sección (p. ej. «0000-60515 Depreciation» al importar Utilities)."""
    salida: list[str] = []
    for a in avisos:
        m = re.match(r"^«\s*0000-(\d{5})", a)
        if m and not any(f"-0000-{m.group(1)}-" in (x.codigo_corporativo or "") for x in candidatas):
            continue
        salida.append(a)
    return salida


def _linea_de_hoja(  # type: ignore[no-untyped-def]
    candidatas: Sequence[LineaReporte],
    dep: str,
    cuenta: str,
    nombre: str,
    alias: dict[str, str] | None = None,
):
    """La línea de una hoja de detalle: mismo número de cuenta y nombre (el título de la hoja viene
    cortado a 31 letras, así que también vale que el nombre de la línea empiece igual). `alias`: los
    de la sección, para las hojas con el nombre escrito distinto."""
    dep, cuenta = _destino_de_hoja(dep, cuenta)
    propio = normalizar(nombre)
    # primero el nombre tal cual (un alias de la sección puede apuntar a otra versión del reporte);
    # el alias solo se usa si el nombre propio no encuentra línea
    objetivos = [propio] + ([alias[propio]] if alias and propio in alias else [])
    # hojas sin número de cuenta (Cafeteria): se emparejan por nombre entre las líneas de su departamento
    patron = f"-{dep}-{cuenta}-" if cuenta else f"-{dep}-"
    mismas = [x for x in candidatas if patron in (x.codigo_corporativo or "")]
    for objetivo in objetivos:
        exacta = next((x for x in mismas if normalizar(x.descripcion) == objetivo), None)
        if exacta is not None:
            return exacta
    for objetivo in objetivos:
        parcial = next(
            (
                x
                for x in mismas
                # una línea «PH» es otra cuenta: solo empareja con una hoja que también es «PH»
                if normalizar(x.descripcion).endswith("ph") == objetivo.endswith("ph")
                and (
                    normalizar(x.descripcion).startswith(objetivo)
                    or objetivo.startswith(normalizar(x.descripcion))
                )
            ),
            None,
        )
        if parcial is not None:
            return parcial
    return None


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
    alias: dict[str, str] | None = None,
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
        quitar_partidas,
        TOLERANCIA_SUMA,
    )
    from fpa.servicios.presupuesto_consumo import (  # noqa: PLC0415 (evita el ciclo de imports)
        consumo_budget,
        guardar_consumo_importado,
    )

    atendidas: set[int] = set()
    importadas = 0
    # líneas que también traen una hoja de partidas en este libro (Water & Sewer: consumo + partidas)
    con_hoja_de_partidas = {
        linea_h.id
        for h in leido.partidas
        if h.partidas
        and (linea_h := _linea_de_hoja(candidatas, h.departamento, h.cuenta, h.nombre, alias)) is not None
    }
    for hoja in leido.partidas:
        if (
            hoja.departamento in DEPARTAMENTOS_COMPARTIDOS
            and hoja.cuenta
            and not any(
                "-{}-{}-".format(*_destino_de_hoja(hoja.departamento, hoja.cuenta)) in (x.codigo_corporativo or "")
                for x in candidatas
            )
        ):
            continue  # el departamento es compartido: esta hoja es de otra sección
        if hoja.departamento in DEPARTAMENTOS_COMPARTIDOS and not hoja.cuenta and (
            _linea_de_hoja(candidatas, hoja.departamento, hoja.cuenta, hoja.nombre, alias) is None
        ):
            continue  # hoja sin número de cuenta (Cafeteria) que no es de esta sección
        if solo_linea is not None:
            de_esta = _linea_de_hoja(candidatas, hoja.departamento, hoja.cuenta, hoja.nombre, alias)
            if de_esta is None or de_esta.id != solo_linea:
                continue
        # Una hoja de partidas que no cuadra con su Total Expense (Depreciation, IVA, Income Tax) no se
        # importa: sus avisos de lectura no aportan, solo el motivo por el que se descarta.
        descartada = hoja.consumo is None and bool(hoja.partidas) and not _cuadra_con_su_total(hoja)[0]
        if not descartada:
            res.avisos.extend(hoja.avisos)
        if hoja.consumo is not None:
            linea = _linea_de_hoja(candidatas, hoja.departamento, hoja.cuenta, hoja.nombre, alias)
            if linea is None:
                res.avisos.append(f"«{hoja.hoja}» no tiene línea en el reporte; se ignora")
                continue
            atendidas.add(linea.id)
            if visibles is not None and linea.id not in visibles:
                res.avisos.append(f"«{linea.descripcion}» está fuera de tu alcance; se omite")
                continue
            captura_previa = db.scalar(
                select(LineaPresupuestoCaptura).where(
                    LineaPresupuestoCaptura.ciclo_id == ciclo.id,
                    LineaPresupuestoCaptura.linea_id == linea.id,
                )
            )
            if (
                linea.id not in con_hoja_de_partidas
                and captura_previa is not None
                and captura_previa.usa_partidas
            ):
                # la cuenta ya no es por partidas (p. ej. Diesel, que se había importado como una partida)
                quitar_partidas(
                    db,
                    organizacion_id=organizacion_id,
                    hotel_id=hotel_id,
                    usuario_id=usuario_id,
                    ciclo_id=ciclo.id,
                    linea_id=linea.id,
                    visibles=visibles,
                )
            guardar_consumo_importado(
                db,
                organizacion_id=organizacion_id,
                hotel_id=hotel_id,
                usuario_id=usuario_id,
                ciclo_id=ciclo.id,
                linea_id=linea.id,
                unidad=hoja.consumo.unidad,
                bloques=hoja.consumo.bloques,
                visibles=visibles,
            )
            importadas += 1
            continue
        if not hoja.partidas:
            continue
        linea = _linea_de_hoja(candidatas, hoja.departamento, hoja.cuenta, hoja.nombre, alias)
        if linea is None:
            res.avisos.append(f"«{hoja.hoja}» no tiene línea en el reporte; se ignora")
            continue
        cuadra, suma_hoja, total_hoja = _cuadra_con_su_total(hoja)
        if not cuadra:
            res.avisos.append(
                f"«{hoja.hoja.strip()}»: no se importa por partidas porque sus partidas suman {suma_hoja:,.2f} y "
                f"su Total Expense dice {total_hoja:,.2f}; el Budget de «{linea.descripcion}» se toma del Excel"
            )
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
        captura_mixta = db.scalar(
            select(LineaPresupuestoCaptura).where(
                LineaPresupuestoCaptura.ciclo_id == ciclo.id,
                LineaPresupuestoCaptura.linea_id == linea.id,
            )
        )
        if captura_mixta is not None and captura_mixta.usa_consumo:  # Water: consumo + partidas
            mio = [a + b for a, b in zip(mio, consumo_budget(db, captura_mixta.id, periodos), strict=True)]
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
            if abs(c.diferencia) >= TOLERANCIA_SUMA:
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
