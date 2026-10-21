"""Importes del Variance agrupados por **departamento de la cuenta** (catálogo oficial, `depto_ef`).

Sale de las mismas cuentas vinculadas y del mismo signo que el Actual del reporte: el importe de una
cuenta en un mes es `signo del vínculo × neto del mes` (positivo tanto en ingresos como en gastos,
como en el reporte de Contraloría). Se agrupa por `depto_ef` y por tipo (`grupo_ef`).

Límites que la pantalla debe decir (no se calculan aquí):
- Budget y variación **no** existen por departamento: el Budget es por línea del reporte.
- Las cuentas vinculadas sin departamento (o sin tipo) se reportan aparte, no se ocultan.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, periodos_ytd
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.saldos import RepositorioSaldos
from fpa.servicios.actual import version_de_mapeo

CERO = Decimal("0")
SIN_DEPARTAMENTO = None  # clave de la fila «Sin departamento»

# `grupo_ef` del catálogo de Novohit -> tipo del reporte. Lo que no esté aquí cae en «otros».
TIPOS = ("ingreso", "nomina", "operacion", "costo", "otros", "sin_tipo")
GASTOS = ("nomina", "operacion", "costo", "otros")
_TIPO_DE_GRUPO = {
    "INCOME": "ingreso",
    "PAYROLL EXPENS": "nomina",
    "OPS EXPENSES": "operacion",
    "COST OF GOODS": "costo",
    "OTHER EXPENSES": "otros",
}


def tipo_de_grupo(grupo_ef: str | None) -> str:
    if grupo_ef is None or not grupo_ef.strip():
        return "sin_tipo"
    return _TIPO_DE_GRUPO.get(grupo_ef.strip().upper(), "otros")


@dataclass(frozen=True)
class DatosCuenta:
    descripcion: str | None
    departamento: str | None
    grupo_ef: str | None


@dataclass
class Importes:
    mes: Decimal = CERO
    ytd: Decimal = CERO

    def sumar(self, mes: Decimal, ytd: Decimal) -> None:
        self.mes += mes
        self.ytd += ytd


@dataclass
class CuentaDeDepartamento:
    codigo: str
    descripcion: str | None
    tipo: str
    mes: Decimal = CERO
    ytd: Decimal = CERO
    n_lineas: int = 0


@dataclass
class FilaDepartamento:
    departamento: str | None
    por_tipo: dict[str, Importes] = field(default_factory=dict)
    cuentas: dict[str, CuentaDeDepartamento] = field(default_factory=dict)

    def importes(self, tipo: str) -> Importes:
        return self.por_tipo.setdefault(tipo, Importes())

    @property
    def ingreso(self) -> Importes:
        return self.por_tipo.get("ingreso", Importes())

    @property
    def gasto(self) -> Importes:
        total = Importes()
        for tipo in GASTOS:
            e = self.por_tipo.get(tipo)
            if e is not None:
                total.sumar(e.mes, e.ytd)
        return total


@dataclass
class ResultadoDepartamentos:
    periodo: str
    version_mapeo_id: int
    periodos_ytd: list[str]
    periodos_sin_datos: list[str]
    filas: list[FilaDepartamento]
    cuentas_vinculadas: int
    cuentas_sin_departamento: int
    cuentas_sin_tipo: int


def agrupar(
    vinculos: Iterable[tuple[int, str, int]],
    netos_por_mes: Mapping[str, Mapping[str, Decimal]],
    *,
    periodo: str,
    meses: list[str],
    catalogo: Mapping[str, DatosCuenta],
) -> list[FilaDepartamento]:
    """Función pura: agrupa por departamento y tipo. Un vínculo suma una vez (como el Variance)."""
    filas: dict[str | None, FilaDepartamento] = {}
    netos_mes = netos_por_mes.get(periodo, {})
    for _linea, codigo, signo in vinculos:
        if signo not in (1, -1):
            raise ValueError(f"Signo inválido {signo!r} en la cuenta {codigo}")
        datos = catalogo.get(codigo, DatosCuenta(None, None, None))
        departamento = (datos.departamento or "").strip() or SIN_DEPARTAMENTO
        tipo = tipo_de_grupo(datos.grupo_ef)
        mes = signo * netos_mes.get(codigo, CERO)
        ytd = sum((signo * netos_por_mes.get(m, {}).get(codigo, CERO) for m in meses), CERO)
        fila = filas.setdefault(departamento, FilaDepartamento(departamento))
        fila.importes(tipo).sumar(mes, ytd)
        cuenta = fila.cuentas.setdefault(
            codigo, CuentaDeDepartamento(codigo, datos.descripcion, tipo)
        )
        cuenta.mes += mes
        cuenta.ytd += ytd
        cuenta.n_lineas += 1
    return sorted(
        filas.values(),
        key=lambda f: (
            f.departamento is None,
            -(f.gasto.ytd + f.ingreso.ytd),
            f.departamento or "",
        ),
    )


def importes_por_departamento(
    db: Session,
    *,
    hotel_id: int,
    periodo: str,
    version_mapeo_id: int | None = None,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> ResultadoDepartamentos:
    """`LookupError` si no hay mapeo aprobado (o la versión pedida no existe)."""
    mapeo = version_de_mapeo(db, hotel_id, version_mapeo_id)
    vinculos = [
        (v.linea_id, v.cuenta_codigo, v.signo)
        for v in RepositorioMapeo(db, hotel_id).vinculos(mapeo.id)
    ]
    repo_saldos = RepositorioSaldos(db, hotel_id)
    con_datos = set(repo_saldos.periodos())
    meses = periodos_ytd(periodo, mes_inicio)
    netos = {
        m: {s.cuenta_codigo: s.neto for s in repo_saldos.del_periodo(m)}
        for m in meses
        if m in con_datos
    }
    catalogo = {
        c.codigo: DatosCuenta(c.descripcion, c.depto_ef, c.grupo_ef)
        for c in RepositorioCatalogo(db, hotel_id).todas()
    }
    filas = agrupar(vinculos, netos, periodo=periodo, meses=meses, catalogo=catalogo)
    cuentas = {codigo for _, codigo, _ in vinculos}
    return ResultadoDepartamentos(
        periodo=periodo,
        version_mapeo_id=mapeo.id,
        periodos_ytd=meses,
        periodos_sin_datos=[m for m in meses if m not in con_datos],
        filas=filas,
        cuentas_vinculadas=len(cuentas),
        cuentas_sin_departamento=sum(
            1
            for c in cuentas
            if not (catalogo.get(c, DatosCuenta(None, None, None)).departamento or "").strip()
        ),
        cuentas_sin_tipo=sum(
            1
            for c in cuentas
            if tipo_de_grupo(catalogo.get(c, DatosCuenta(None, None, None)).grupo_ef) == "sin_tipo"
        ),
    )
