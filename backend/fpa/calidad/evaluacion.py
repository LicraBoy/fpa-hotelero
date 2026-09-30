"""Calidad de datos de una lectura (Blueprint §31). Funciones puras: no tocan la base de datos.

Cada control produce un `ControlCalidad`:
- `error`  -> la carga se rechaza (los datos no son confiables).
- `aviso`  -> la carga se acepta y el aviso queda guardado para que Contraloría lo revise.
- `ok`     -> el control pasó.

Qué es error y qué es aviso se decidió con los archivos reales de Torres: las filas repetidas
exactas (14 en el CON130, 5 en el Variance) y los importes negativos (reversos y ajustes: 257 y 92)
existen legítimamente, por eso son avisos y no errores.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from fpa.ingesta.contrato import CERO, ResultadoLectura

_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_RE_PERIODO = re.compile(
    r"periodo\s+([a-zA-ZÁÉÍÓÚáéíóúñÑ]+)\s+(\d{4})\s+a\s+([a-zA-ZÁÉÍÓÚáéíóúñÑ]+)\s+(\d{4})"
)
_RE_ASIENTO = re.compile(r"^(\d+)\.\d+\.\d+$")
_MAX_EJEMPLOS = 10


class Severidad(StrEnum):
    OK = "ok"
    AVISO = "aviso"
    ERROR = "error"


@dataclass
class ControlCalidad:
    codigo: str
    severidad: Severidad
    resumen: str
    ejemplos: list[str] = field(default_factory=list)

    def a_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "severidad": self.severidad.value,
            "resumen": self.resumen,
            "ejemplos": self.ejemplos,
        }


@dataclass
class ReporteCalidad:
    fuente: str | None
    controles: list[ControlCalidad] = field(default_factory=list)

    @property
    def errores(self) -> list[ControlCalidad]:
        return [c for c in self.controles if c.severidad == Severidad.ERROR]

    @property
    def avisos(self) -> list[ControlCalidad]:
        return [c for c in self.controles if c.severidad == Severidad.AVISO]

    @property
    def aprobado(self) -> bool:
        return not self.errores

    def motivos_de_rechazo(self) -> list[str]:
        """Mensajes claros para el usuario: el resumen de cada error y algunos ejemplos."""
        motivos: list[str] = []
        for control in self.errores:
            motivos.append(control.resumen)
            motivos.extend(control.ejemplos[:5])
        return motivos

    def a_dict(self) -> dict[str, Any]:
        return {
            "fuente": self.fuente,
            "aprobado": self.aprobado,
            "controles": [c.a_dict() for c in self.controles],
        }


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_acentos if not unicodedata.combining(c))


def periodo_del_encabezado(texto: str | None) -> tuple[date, date] | None:
    """`Periodo Septiembre 2026 a Septiembre 2026, ...` -> (2026-09-01, 2026-09-30)."""
    if not texto:
        return None
    m = _RE_PERIODO.search(_normalizar(texto))
    if not m:
        return None
    mes_i, anio_i, mes_f, anio_f = (
        _MESES.get(m.group(1)),
        int(m.group(2)),
        _MESES.get(m.group(3)),
        int(m.group(4)),
    )
    if mes_i is None or mes_f is None:
        return None
    inicio = date(anio_i, mes_i, 1)
    fin = date(anio_f, mes_f, calendar.monthrange(anio_f, mes_f)[1])
    return (inicio, fin) if inicio <= fin else None


def _ok(codigo: str, resumen: str) -> ControlCalidad:
    return ControlCalidad(codigo, Severidad.OK, resumen)


def evaluar(
    resultado: ResultadoLectura,
    *,
    periodos_esperados: Collection[str] | None = None,
    cuentas_conocidas: Collection[str] | None = None,
) -> ReporteCalidad:
    """Evalúa una lectura.

    `periodos_esperados` (`AAAA-MM`): si el usuario declara de qué meses es el archivo, todo
    movimiento fuera de ellos es error. `cuentas_conocidas`: catálogo ya existente, para avisar
    de cuentas nuevas (si viene vacío, es la primera carga y no se avisa).
    """
    rep = ReporteCalidad(fuente=resultado.fuente.value if resultado.fuente else None)
    movs = resultado.movimientos
    c = rep.controles

    # 1) Errores que el propio lector detectó (montos o fechas inválidos, cuentas repetidas...)
    if resultado.errores:
        c.append(
            ControlCalidad(
                "lectura_sin_errores",
                Severidad.ERROR,
                f"El archivo tiene {len(resultado.errores)} error(es) de lectura",
                resultado.errores[:_MAX_EJEMPLOS],
            )
        )
    else:
        c.append(_ok("lectura_sin_errores", "El archivo se leyó sin errores"))

    # 2) Débito = Crédito (solo fuentes que son un libro completo)
    if resultado.controla_balance:
        if resultado.cuadra_debito_credito:
            c.append(_ok("balance_debito_credito", f"Débito = Crédito = {resultado.total_debito}"))
        else:
            c.append(
                ControlCalidad(
                    "balance_debito_credito",
                    Severidad.ERROR,
                    f"Débito total {resultado.total_debito} distinto de Crédito total "
                    f"{resultado.total_credito} (diferencia "
                    f"{resultado.total_debito - resultado.total_credito})",
                )
            )

    # 3) Total de cada cuenta = suma de sus movimientos (solo el CON130 trae filas "Total")
    con_total = [q for q in resultado.cuentas.values() if q.total_verificado is not None]
    sin_total = [q for q in resultado.cuentas.values() if q.total_verificado is None]
    if resultado.cuentas and (con_total or resultado.controla_balance):
        fallan = [q for q in con_total if q.total_verificado is False]
        if fallan:
            c.append(
                ControlCalidad(
                    "totales_por_cuenta",
                    Severidad.ERROR,
                    f"{len(fallan)} cuenta(s) con Total distinto de la suma de sus movimientos",
                    [
                        f"{q.codigo}: Total {q.total_debito_reporte}/{q.total_credito_reporte} vs "
                        f"movimientos {q.suma_debito}/{q.suma_credito}"
                        for q in fallan[:_MAX_EJEMPLOS]
                    ],
                )
            )
        elif sin_total:
            c.append(
                ControlCalidad(
                    "totales_por_cuenta",
                    Severidad.AVISO,
                    f"{len(sin_total)} cuenta(s) sin fila 'Total' para verificar",
                    [q.codigo for q in sin_total[:_MAX_EJEMPLOS]],
                )
            )
        else:
            c.append(
                _ok("totales_por_cuenta", f"Los {len(con_total)} totales por cuenta coinciden")
            )

    # 4) Fechas dentro del periodo que declara el propio reporte (encabezado del CON130)
    rango = periodo_del_encabezado(resultado.periodo_texto)
    if resultado.periodo_texto and rango is None:
        c.append(
            ControlCalidad(
                "fechas_en_periodo_del_encabezado",
                Severidad.AVISO,
                "No se pudo interpretar el periodo del encabezado del reporte",
                [resultado.periodo_texto[:120]],
            )
        )
    elif rango is not None:
        fuera = [m for m in movs if not (rango[0] <= m.fecha <= rango[1])]
        if fuera:
            c.append(
                ControlCalidad(
                    "fechas_en_periodo_del_encabezado",
                    Severidad.ERROR,
                    f"{len(fuera)} movimiento(s) con fecha fuera del periodo del reporte "
                    f"({rango[0]} a {rango[1]})",
                    [
                        f"fila {m.fila}: {m.fecha} ({m.cuenta_codigo})"
                        for m in fuera[:_MAX_EJEMPLOS]
                    ],
                )
            )
        else:
            c.append(
                _ok(
                    "fechas_en_periodo_del_encabezado",
                    f"Todas las fechas caen en {rango[0]} a {rango[1]}",
                )
            )

    # 5) Fechas dentro de los periodos que declaró el usuario al cargar
    if periodos_esperados:
        esperados = set(periodos_esperados)
        fuera = [m for m in movs if m.periodo not in esperados]
        if fuera:
            c.append(
                ControlCalidad(
                    "fechas_en_periodos_declarados",
                    Severidad.ERROR,
                    f"{len(fuera)} movimiento(s) fuera de los periodos declarados "
                    f"({', '.join(sorted(esperados))})",
                    [f"fila {m.fila}: {m.fecha}" for m in fuera[:_MAX_EJEMPLOS]],
                )
            )
        else:
            c.append(_ok("fechas_en_periodos_declarados", "Las fechas coinciden con lo declarado"))

    # 6) Avisos propios del lector (mes en texto distinto, cuenta con dos nombres, sin importe...)
    if resultado.avisos:
        c.append(
            ControlCalidad(
                "avisos_de_lectura",
                Severidad.AVISO,
                f"El lector dejó {len(resultado.avisos)} aviso(s)",
                resultado.avisos[:_MAX_EJEMPLOS],
            )
        )

    # 7) Cuentas nuevas respecto del catálogo existente
    if cuentas_conocidas:
        nuevas = sorted(set(resultado.cuentas) - set(cuentas_conocidas))
        if nuevas:
            c.append(
                ControlCalidad(
                    "cuentas_nuevas",
                    Severidad.AVISO,
                    f"{len(nuevas)} cuenta(s) que no estaban en el catálogo",
                    nuevas[:_MAX_EJEMPLOS],
                )
            )
        else:
            c.append(_ok("cuentas_nuevas", "Todas las cuentas ya estaban en el catálogo"))

    # 8) Filas repetidas exactas: existen legítimamente, se avisa pero no se rechaza
    repetidas = Counter(
        (m.cuenta_codigo, m.asiento, m.fecha, m.numero, m.concepto, m.debito, m.credito)
        for m in movs
    )
    extra = sum(v - 1 for v in repetidas.values() if v > 1)
    if extra:
        c.append(
            ControlCalidad(
                "filas_repetidas",
                Severidad.AVISO,
                f"{extra} fila(s) repetidas exactamente (pueden ser legítimas)",
                [
                    f"{k[0]} asiento {k[1]} {k[2]} {k[4]!r} D={k[5]} C={k[6]} (x{v})"
                    for k, v in repetidas.items()
                    if v > 1
                ][:_MAX_EJEMPLOS],
            )
        )

    # 9) Importes negativos: reversos y ajustes (existen en los datos reales), se avisa
    negativos = [m for m in movs if m.debito < CERO or m.credito < CERO]
    if negativos:
        c.append(
            ControlCalidad(
                "importes_negativos",
                Severidad.AVISO,
                f"{len(negativos)} movimiento(s) con importe negativo (reversos o ajustes)",
                [
                    f"fila {m.fila}: {m.cuenta_codigo} D={m.debito} C={m.credito}"
                    for m in negativos[:5]
                ],
            )
        )

    # 10) Un movimiento con Débito y Crédito a la vez es raro
    ambos = [m for m in movs if m.debito > CERO and m.credito > CERO]
    if ambos:
        c.append(
            ControlCalidad(
                "debito_y_credito_a_la_vez",
                Severidad.AVISO,
                f"{len(ambos)} movimiento(s) con Débito y Crédito a la vez",
                [f"fila {m.fila}: {m.cuenta_codigo}" for m in ambos[:_MAX_EJEMPLOS]],
            )
        )

    # 11) El primer número del asiento (9.2.15) coincide con el mes de la fecha (verificado al 100%
    #     en septiembre y en julio–agosto); los asientos de inventario (números sueltos) no aplican.
    desfasados = []
    for m in movs:
        a = _RE_ASIENTO.match(m.asiento)
        if a and int(a.group(1)) != m.fecha.month:
            desfasados.append(m)
    if desfasados:
        c.append(
            ControlCalidad(
                "asiento_y_mes",
                Severidad.AVISO,
                f"{len(desfasados)} asiento(s) con primer número distinto del mes de la fecha",
                [
                    f"fila {m.fila}: asiento {m.asiento} fecha {m.fecha}"
                    for m in desfasados[:_MAX_EJEMPLOS]
                ],
            )
        )
    return rep
