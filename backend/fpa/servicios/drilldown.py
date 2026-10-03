"""Drill-down del reporte: línea -> cuentas -> movimientos -> asiento.

La propiedad que se garantiza (y se prueba): **la suma de lo que se muestra en cada nivel es la
cifra del nivel anterior**. Los movimientos de una cuenta suman su neto; las cuentas de una línea
suman su Actual (cada una con el signo del mapeo); los componentes de un total suman el total.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, periodos_ytd
from fpa.calculo.totales import completar_con_totales
from fpa.modelos.cargas import Movimiento
from fpa.repositorios.cargas import RepositorioCargas
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.repositorios.saldos import RepositorioSaldos
from fpa.servicios.actual import actual_del_periodo, actual_ytd_del_periodo, version_de_mapeo
from fpa.servicios.reglas_suma import lineas_aditivas, reglas_como_mapa

Bloque = Literal["mes", "ytd"]
CERO = Decimal("0")
LIMITE_MAXIMO = 200
LIMITE_ASIENTO = 500


class CursorInvalido(ValueError):
    """El cursor no es uno que esta API haya entregado."""


def periodos_del_bloque(
    periodo: str, bloque: Bloque, mes_inicio: int = MES_INICIO_POR_DEFECTO
) -> list[str]:
    return [periodo] if bloque == "mes" else periodos_ytd(periodo, mes_inicio)


# --- Cursor -----------------------------------------------------------------------------------


def codificar_cursor(ultimo_id: int) -> str:
    crudo = json.dumps({"v": 1, "id": ultimo_id}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def decodificar_cursor(cursor: str) -> int:
    try:
        relleno = "=" * (-len(cursor) % 4)
        datos = json.loads(base64.urlsafe_b64decode(cursor + relleno))
        ultimo = datos["id"]
        if datos.get("v") != 1 or isinstance(ultimo, bool) or not isinstance(ultimo, int):
            raise CursorInvalido("Cursor inválido")
        if not 0 <= ultimo <= 2_147_483_647:
            raise CursorInvalido("Cursor inválido")
        return ultimo
    except (binascii.Error, ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise CursorInvalido("Cursor inválido") from None


# --- Línea -> cuentas / componentes -----------------------------------------------------------


@dataclass(frozen=True)
class CuentaDesglose:
    cuenta_codigo: str
    descripcion: str | None
    signo: int
    neto: Decimal  # Débito − Crédito de la cuenta en el bloque
    aporte: Decimal  # signo × neto: lo que pone la cuenta en la línea
    n_movimientos: int


@dataclass(frozen=True)
class ComponenteDesglose:
    linea_id: int
    descripcion: str
    tipo: str
    signo: int
    importe: Decimal  # lo que aporta el componente (ya multiplicado por su factor), sin signo
    factor: Decimal = Decimal("1")  # 1 salvo en las líneas «16 % de otra línea»


@dataclass
class Desglose:
    linea_id: int
    descripcion: str
    tipo: str
    periodo: str
    bloque: Bloque
    periodos: list[str]
    cifra: Decimal  # lo que dice el reporte para la línea
    suma: Decimal  # lo que suman las partes mostradas
    cuentas: list[CuentaDesglose] = field(default_factory=list)
    componentes: list[ComponenteDesglose] = field(default_factory=list)

    @property
    def cuadra(self) -> bool:
        return self.suma == self.cifra


def desglose_de_linea(
    db: Session,
    *,
    hotel_id: int,
    periodo: str,
    linea_id: int,
    bloque: Bloque,
    version_mapeo_id: int | None = None,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> Desglose:
    """Desglosa una línea. `LookupError` si no existe en la estructura del mapeo."""
    mapeo = version_de_mapeo(db, hotel_id, version_mapeo_id)
    lineas = {x.id: x for x in RepositorioReporte(db, hotel_id).lineas(mapeo.version_estructura_id)}
    linea = lineas.get(linea_id)
    if linea is None or linea.tipo == "seccion":
        raise LookupError("Línea no encontrada")
    periodos = periodos_del_bloque(periodo, bloque, mes_inicio)
    reglas = reglas_como_mapa(db, hotel_id, mapeo.version_estructura_id)

    if bloque == "mes":
        base = actual_del_periodo(db, hotel_id=hotel_id, periodo=periodo, version_mapeo_id=mapeo.id)
    else:
        base = actual_ytd_del_periodo(
            db,
            hotel_id=hotel_id,
            periodo=periodo,
            version_mapeo_id=mapeo.id,
            mes_inicio=mes_inicio,
        ).por_linea
    vinculos = RepositorioMapeo(db, hotel_id).vinculos(mapeo.id)
    aditivas = lineas_aditivas(reglas, {v.linea_id for v in vinculos})
    todo = completar_con_totales(reglas, base, aditivas)
    cifra = todo.get(linea_id, CERO)
    salida = Desglose(
        linea_id=linea.id,
        descripcion=linea.descripcion,
        tipo=linea.tipo,
        periodo=periodo,
        bloque=bloque,
        periodos=periodos,
        cifra=cifra,
        suma=CERO,
    )

    if linea_id in reglas:
        for componente_id, coeficiente in reglas[linea_id]:
            componente = lineas[componente_id]
            factor = abs(Decimal(coeficiente))
            valor = todo.get(componente_id, CERO)
            # con factor 1 el importe es el del componente tal cual (2 decimales); con otro factor
            # (el 16 % de otra línea) se redondea a centavos, como se muestra
            aporte = valor if factor == 1 else (valor * factor).quantize(Decimal("0.01"))
            salida.componentes.append(
                ComponenteDesglose(
                    componente.id,
                    componente.descripcion,
                    componente.tipo,
                    1 if coeficiente > 0 else -1,
                    aporte,
                    factor.normalize(),
                )
            )
        salida.suma = sum((c.signo * c.importe for c in salida.componentes), CERO)
        if linea_id not in aditivas:
            return salida

    saldos: dict[str, tuple[Decimal, int]] = {}
    repo_saldos = RepositorioSaldos(db, hotel_id)
    for p in periodos:
        for s in repo_saldos.del_periodo(p):
            neto, n = saldos.get(s.cuenta_codigo, (CERO, 0))
            saldos[s.cuenta_codigo] = (neto + s.neto, n + s.n_movimientos)
    nombres = {c.codigo: c.descripcion for c in RepositorioCatalogo(db, hotel_id).todas()}
    for v in vinculos:
        if v.linea_id != linea_id:
            continue
        neto, n = saldos.get(v.cuenta_codigo, (CERO, 0))
        salida.cuentas.append(
            CuentaDesglose(
                v.cuenta_codigo, nombres.get(v.cuenta_codigo), v.signo, neto, v.signo * neto, n
            )
        )
    salida.cuentas.sort(key=lambda c: c.cuenta_codigo)
    salida.suma += sum((c.aporte for c in salida.cuentas), CERO)
    return salida


# --- Cuenta -> movimientos (por cursor) -------------------------------------------------------


@dataclass(frozen=True)
class ResumenCuenta:
    n_movimientos: int
    debito: Decimal
    credito: Decimal

    @property
    def neto(self) -> Decimal:
        return self.debito - self.credito


@dataclass
class PaginaMovimientos:
    cuenta_codigo: str
    descripcion: str | None
    periodo: str
    bloque: Bloque
    periodos: list[str]
    resumen: ResumenCuenta
    movimientos: list[Movimiento]
    siguiente_cursor: str | None


def resumen_de_cuenta(
    db: Session, hotel_id: int, periodos: list[str], cuenta_codigo: str
) -> ResumenCuenta:
    """Totales de la cuenta, de los saldos mensuales (precalculados al cargar)."""
    n, debito, credito = 0, CERO, CERO
    repo = RepositorioSaldos(db, hotel_id)
    for p in periodos:
        for s in repo.del_periodo(p):
            if s.cuenta_codigo == cuenta_codigo:
                n += s.n_movimientos
                debito += s.suma_debito
                credito += s.suma_credito
    return ResumenCuenta(n, debito, credito)


def movimientos_de_cuenta(
    db: Session,
    *,
    hotel_id: int,
    periodo: str,
    bloque: Bloque,
    cuenta_codigo: str,
    cursor: str | None = None,
    limite: int = 50,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> PaginaMovimientos:
    """Una página de movimientos. `CursorInvalido` si el cursor no es de esta API."""
    if not 1 <= limite <= LIMITE_MAXIMO:
        raise ValueError(f"El límite debe estar entre 1 y {LIMITE_MAXIMO}")
    despues = decodificar_cursor(cursor) if cursor else None
    periodos = periodos_del_bloque(periodo, bloque, mes_inicio)
    filas = RepositorioCargas(db, hotel_id).movimientos_de_cuenta(
        periodos, cuenta_codigo, despues, limite + 1
    )
    hay_mas = len(filas) > limite
    pagina = filas[:limite]
    cuenta = {c.codigo: c for c in RepositorioCatalogo(db, hotel_id).todas()}.get(cuenta_codigo)
    return PaginaMovimientos(
        cuenta_codigo=cuenta_codigo,
        descripcion=cuenta.descripcion if cuenta else None,
        periodo=periodo,
        bloque=bloque,
        periodos=periodos,
        resumen=resumen_de_cuenta(db, hotel_id, periodos, cuenta_codigo),
        movimientos=pagina,
        siguiente_cursor=codificar_cursor(pagina[-1].id) if hay_mas and pagina else None,
    )


# --- Asiento ----------------------------------------------------------------------------------


@dataclass
class VistaAsiento:
    asiento: str
    periodo: str
    movimientos: list[Movimiento]
    debito: Decimal
    credito: Decimal
    truncado: bool

    @property
    def cuadra(self) -> bool:
        """Débito = Crédito (un asiento completo). En el Variance (solo cuentas de resultados)
        un asiento puede no cuadrar: es un subconjunto del libro."""
        return self.debito == self.credito


def vista_de_asiento(db: Session, *, hotel_id: int, periodo: str, asiento: str) -> VistaAsiento:
    filas = RepositorioCargas(db, hotel_id).movimientos_de_asiento(
        periodo, asiento, LIMITE_ASIENTO + 1
    )
    truncado = len(filas) > LIMITE_ASIENTO
    filas = filas[:LIMITE_ASIENTO]
    return VistaAsiento(
        asiento=asiento,
        periodo=periodo,
        movimientos=filas,
        debito=sum((m.debito for m in filas), CERO),
        credito=sum((m.credito for m in filas), CERO),
        truncado=truncado,
    )
