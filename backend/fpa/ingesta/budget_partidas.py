"""Lector de las hojas de detalle por cuenta del Budget de Mazatlán (p. ej. `0111-60055 Other Fringe`).

Cada hoja es una tabla de **partidas** (de la fila 9 hasta `Total Expense`):

    B Item · D Qty of Items · E Unit of Measure · F Cost · G Extended Cost (= Qty × Cost)
    H Monthly · I Md Turn · J Md Pts · K Rm Night · L Seasonal   (una «X» marca el método)
    M..X  JUL … JUN (la distribución mensual) · Y Total

y, abajo, la fila `Mthly` (columna J) con la **inflación mensual** (M..X), que SÍ entra al Budget:
Budget del mes = distribución × (1 + inflación). La fórmula nunca se evalúa: se leen los valores
guardados.

El método se decide por los datos, no solo por la «X»: una partida con 12 meses iguales a extendido ÷ 12
es `mensual`; si trae otra forma es `estacional` (y se avisa si la hoja decía Monthly); las que marcan
Md Turn / Md Pts / Rm Night se importan como `importada` (de solo lectura: no se reimplementa la
estadística de camarista).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from fpa.ingesta.budget_other_income import _dec, normalizar

COL_ITEM, COL_QTY, COL_UNIDAD, COL_COSTO, COL_EXTENDIDO = 1, 3, 4, 5, 6
COL_MENSUAL, COL_ESTADISTICAS, COL_ESTACIONAL = 7, (8, 9, 10), 11
COL_PRIMER_MES, COL_ETIQUETA_INFLACION = 12, 9
MESES = 12
_COLS = COL_PRIMER_MES + MESES + 1
_TOLERANCIA = Decimal("0.01")
_RE_HOJA = re.compile(r"^(\d{4})-(\d{5})\s+(.+)$")
CERO = Decimal(0)


@dataclass(frozen=True)
class PartidaLeida:
    concepto: str
    cantidad: Decimal
    unidad: str | None
    costo: Decimal
    metodo: str  # mensual | estacional | importada
    meses: list[Decimal]
    fila: int


@dataclass
class PartidasLeidas:
    hoja: str
    departamento: str
    cuenta: str  # número de cuenta (60055)
    nombre: str  # nombre de la cuenta según el título de la hoja (puede venir cortado a 31 letras)
    partidas: list[PartidaLeida] = field(default_factory=list)
    inflacion: list[Decimal] = field(default_factory=lambda: [CERO] * MESES)
    total_expense: Decimal | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def distribucion(self) -> list[Decimal]:
        return [sum((p.meses[i] for p in self.partidas), CERO) for i in range(MESES)]


def datos_de_hoja(titulo: str) -> tuple[str, str, str] | None:
    """`0111-60055 Other Fringe` -> (`0111`, `60055`, `Other Fringe`); `None` si no es una hoja de cuenta."""
    m = _RE_HOJA.match(titulo.strip())
    return (m.group(1), m.group(2), m.group(3).strip()) if m else None


def _celdas(fila: Sequence[object]) -> list[object]:
    return list(fila) + [None] * (_COLS - len(fila))


def _marca(valor: object) -> bool:
    return str(valor or "").strip().upper() == "X"


def leer_hoja_partidas(titulo: str, filas: Sequence[Sequence[object]]) -> PartidasLeidas:
    """Lee una hoja de detalle ya cargada (`filas`: todas las filas, columnas A en adelante)."""
    datos = datos_de_hoja(titulo)
    if datos is None:
        raise ValueError(f"«{titulo}» no es una hoja de detalle de cuenta")
    res = PartidasLeidas(hoja=titulo, departamento=datos[0], cuenta=datos[1], nombre=datos[2])
    encabezado = next(
        (i for i, f in enumerate(filas[:20]) if normalizar(_celdas(f)[COL_ITEM]) == "item"), None
    )
    if encabezado is None:
        raise ValueError(f"«{titulo}»: no se encontró el encabezado «Item»")
    fin = len(filas)
    for n in range(encabezado + 1, len(filas)):
        c = _celdas(filas[n])
        if normalizar(c[COL_ITEM]) == "totalexpense":
            res.total_expense = _dec(c[COL_EXTENDIDO])
            fin = n
            break
        _leer_partida(res, c, n + 1)
    for fila in filas[fin + 1 :]:
        c = _celdas(fila)
        if normalizar(c[COL_ETIQUETA_INFLACION]) == "mthly":
            res.inflacion = [_dec(c[COL_PRIMER_MES + i]) or CERO for i in range(MESES)]
            break
    else:
        res.avisos.append(f"«{titulo}»: no trae la fila de inflación (Mthly); se toma 0 %")
    if not res.partidas:
        res.avisos.append(f"«{titulo}»: no trae partidas")
    elif res.total_expense is not None:
        suma = sum((p.meses[i] for p in res.partidas for i in range(MESES)), CERO)
        if abs(suma - res.total_expense) > _TOLERANCIA:
            res.avisos.append(
                f"«{titulo}»: las partidas suman {suma:,.2f} y el Total Expense dice {res.total_expense:,.2f}"
            )
    return res


def _leer_partida(res: PartidasLeidas, c: list[object], fila: int) -> None:
    concepto = str(c[COL_ITEM] or "").strip()
    meses = [_dec(c[COL_PRIMER_MES + i]) for i in range(MESES)]
    extendido = _dec(c[COL_EXTENDIDO])
    con_importe = any(m for m in meses if m) or bool(extendido)
    if not concepto:
        if con_importe:
            res.avisos.append(f"«{res.hoja}» fila {fila}: trae importes sin nombre de partida; se ignora")
        return
    if not con_importe:
        return  # renglón vacío de la hoja
    valores = [m or CERO for m in meses]
    cantidad = _dec(c[COL_QTY])
    costo = _dec(c[COL_COSTO])
    if cantidad is None and costo is None:
        cantidad, costo = Decimal(1), extendido or sum(valores, CERO)
    elif cantidad is None or cantidad == 0:
        cantidad = Decimal(1) if cantidad is None else cantidad
        costo = costo if costo is not None else (extendido or CERO)
    elif costo is None:
        costo = (extendido or CERO) / cantidad
    ext = extendido if extendido is not None else cantidad * costo
    if abs(cantidad * costo - ext) > _TOLERANCIA:
        res.avisos.append(
            f"«{res.hoja}» «{concepto[:30]}»: Qty × Cost ({cantidad * costo:,.2f}) no es el Extended Cost ({ext:,.2f})"
        )
    marcada_mensual = _marca(c[COL_MENSUAL])
    if any(_marca(c[i]) for i in COL_ESTADISTICAS):
        metodo = "importada"
    else:
        iguales = all(abs(v - valores[0]) <= _TOLERANCIA for v in valores)
        suma = sum(valores, CERO)
        cuadra = abs(suma - ext) <= _TOLERANCIA
        if iguales and cuadra and valores[0] != 0:
            metodo = "mensual"
        else:
            metodo = "estacional"
            if marcada_mensual:
                res.avisos.append(
                    f"«{res.hoja}» «{concepto[:30]}»: decía Monthly pero sus meses no son iguales; se importa estacional"
                )
    res.partidas.append(
        PartidaLeida(
            concepto=concepto[:120],
            cantidad=cantidad,
            unidad=(str(c[COL_UNIDAD]).strip()[:20] or None) if c[COL_UNIDAD] is not None else None,
            costo=costo,
            metodo=metodo,
            meses=valores,
            fila=fila,
        )
    )


__all__ = ["PartidaLeida", "PartidasLeidas", "datos_de_hoja", "leer_hoja_partidas"]
