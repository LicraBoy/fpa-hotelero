"""Lector del reporte CON130 "Mayor Analítico (movimientos por cuentas)" de Novohit.

El reporte no es una tabla plana: intercala títulos de jerarquía, encabezados de
cuenta, filas "Saldo anterior", movimientos y filas "Total". Este lector
clasifica cada fila y entrega los movimientos, los títulos de la jerarquía de cuentas y los
controles (Débito = Crédito y total por cuenta = suma de sus movimientos).

Reglas (ver Blueprint, sección 12.1):
- Las columnas se ubican a partir del encabezado "# ASIENTO"; las columnas
  auxiliares que Contraloría agrega a la izquierda (mes, fecha, código,
  descripción, F) no se usan.
- Una cuenta con movimientos se abre en la fila que trae el encabezado de la
  cuenta en la columna "# ASIENTO" y "Saldo anterior" en Concepto.
- El Saldo anterior no entra al cálculo del Actual.
- Un título de jerarquía es una fila con solo un código (y a veces descripción) en la columna
  "# ASIENTO": `1`, `10`, `1000`, `1000001 BANCOS MONEDA NACIONAL`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from fpa.ingesta.contrato import (
    CENTAVO,
    CERO,
    Cuenta,
    Fuente,
    Movimiento,
    ResultadoLectura,
    Titulo,
)
from fpa.ingesta.utilidades import a_dinero, a_fecha, a_texto

__all__ = [
    "Cuenta",
    "Movimiento",
    "ResultadoCon130",
    "Titulo",
    "TotalGrupo",
    "leer_con130",
    "leer_con130_filas",
]

_RE_CUENTA = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*\S)\s*$")
_RE_TITULO = re.compile(r"^(\d+(?:\.\d+)*)(?:\s+(.*\S))?\s*$")
CAMPOS = (
    "asiento",
    "fecha",
    "tp_asiento",
    "operacion",
    "tp_doc",
    "numero",
    "fecha_doc",
    "concepto",
    "debito",
    "credito",
    "saldo",
)


@dataclass
class TotalGrupo:
    descripcion: str
    debito: Decimal
    credito: Decimal
    fila: int


@dataclass
class ResultadoCon130(ResultadoLectura):
    fuente: Fuente | None = Fuente.CON130
    empresa: str | None = None
    periodo_texto: str | None = None
    totales_grupo: list[TotalGrupo] = field(default_factory=list)
    filas_ignoradas: int = 0


def _ubicar_encabezado(filas: Sequence[Sequence[object]]) -> tuple[int, int]:
    """Devuelve (índice de fila, índice de columna) del encabezado '# ASIENTO'."""
    for i, fila in enumerate(filas[:40]):
        for j, celda in enumerate(fila):
            if isinstance(celda, str) and celda.strip().upper() == "# ASIENTO":
                return i, j
    raise ValueError('No se encontró el encabezado "# ASIENTO": no parece un CON130 de Novohit')


def leer_con130(ruta: str | Path, hoja: str | None = None) -> ResultadoCon130:
    wb = load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = wb[hoja] if hoja else wb.worksheets[0]
        filas = [tuple(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()
    return leer_con130_filas(filas)


def leer_con130_filas(filas: Sequence[Sequence[object]]) -> ResultadoCon130:
    res = ResultadoCon130()
    i_enc, c0 = _ubicar_encabezado(filas)

    # Datos de cabecera (antes del encabezado de columnas)
    for fila in filas[:i_enc]:
        for celda in fila:
            if not isinstance(celda, str):
                continue
            texto = celda.strip()
            if texto.lower().startswith("periodo") and res.periodo_texto is None:
                res.periodo_texto = texto
        if res.empresa is None:
            for celda in fila:
                if (
                    isinstance(celda, str)
                    and celda.strip()
                    and not celda.strip().lower().startswith("novohit")
                ):
                    res.empresa = celda.strip()
                    break

    def col(fila: Sequence[object], campo: str) -> object:
        idx = c0 + CAMPOS.index(campo)
        return fila[idx] if idx < len(fila) else None

    abierta: Cuenta | None = None

    def cerrar_sin_total() -> None:
        nonlocal abierta
        if abierta is not None and abierta.total_verificado is None:
            res.avisos.append(f"Cuenta {abierta.codigo} (fila {abierta.fila}) no trae fila 'Total'")
        abierta = None

    for n, fila in enumerate(filas[i_enc + 1 :], start=i_enc + 2):
        asiento_o_cuenta = a_texto(col(fila, "asiento"))
        concepto = a_texto(col(fila, "concepto"))
        fecha = a_fecha(col(fila, "fecha"))
        try:
            debito = a_dinero(col(fila, "debito"))
            credito = a_dinero(col(fila, "credito"))
            saldo = a_dinero(col(fila, "saldo"))
        except ValueError as e:
            res.errores.append(f"Fila {n}: {e}")
            continue

        # 1) Apertura de cuenta: encabezado de cuenta + "Saldo anterior" en la misma fila
        if concepto and concepto.lower() == "saldo anterior":
            m = _RE_CUENTA.match(asiento_o_cuenta or "")
            if not m:
                res.errores.append(f"Fila {n}: 'Saldo anterior' sin encabezado de cuenta")
                continue
            cerrar_sin_total()
            codigo, descripcion = m.group(1), m.group(2)
            if codigo in res.cuentas:
                res.errores.append(f"Fila {n}: la cuenta {codigo} aparece más de una vez")
            abierta = Cuenta(
                codigo=codigo,
                descripcion=descripcion,
                fila=n,
                saldo_anterior=debito if debito is not None else credito,
            )
            res.cuentas[codigo] = abierta
            continue

        # 2) Fila "Total ..."
        if concepto and concepto.lower().startswith("total"):
            if abierta is not None:
                abierta.total_debito_reporte = debito or CERO
                abierta.total_credito_reporte = credito or CERO
                coincide = (
                    abs(abierta.total_debito_reporte - abierta.suma_debito) < CENTAVO
                    and abs(abierta.total_credito_reporte - abierta.suma_credito) < CENTAVO
                )
                abierta.total_verificado = coincide
                if not coincide:
                    res.errores.append(
                        f"Fila {n}: el Total de {abierta.codigo} ({abierta.total_debito_reporte}/"
                        f"{abierta.total_credito_reporte}) no coincide con la suma de sus "
                        "movimientos "
                        f"({abierta.suma_debito}/{abierta.suma_credito})"
                    )
                abierta = None
            else:
                res.totales_grupo.append(TotalGrupo(concepto, debito or CERO, credito or CERO, n))
            continue

        # 3) Movimiento
        if fecha is not None:
            if abierta is None:
                res.errores.append(f"Fila {n}: movimiento sin cuenta abierta")
                continue
            if debito is None and credito is None:
                res.errores.append(f"Fila {n}: movimiento sin Débito ni Crédito")
                continue
            d, c = debito or CERO, credito or CERO
            res.movimientos.append(
                Movimiento(
                    cuenta_codigo=abierta.codigo,
                    cuenta_descripcion=abierta.descripcion,
                    asiento=asiento_o_cuenta or "",
                    fecha=fecha,
                    concepto=concepto,
                    debito=d,
                    credito=c,
                    fila=n,
                    tp_asiento=a_texto(col(fila, "tp_asiento")),
                    operacion=a_texto(col(fila, "operacion")),
                    tp_doc=a_texto(col(fila, "tp_doc")),
                    numero=a_texto(col(fila, "numero")),
                    saldo=saldo,
                )
            )
            abierta.suma_debito += d
            abierta.suma_credito += c
            continue

        # 4) Título de jerarquía: solo código (y a veces descripción) en la columna "# ASIENTO"
        if (
            asiento_o_cuenta
            and concepto is None
            and debito is None
            and credito is None
            and saldo is None
        ):
            t = _RE_TITULO.match(asiento_o_cuenta)
            if t:
                res.titulos.append(Titulo(codigo=t.group(1), descripcion=t.group(2), fila=n))
                continue

        # 5) Filas vacías y todo lo demás
        if any(v is not None and str(v).strip() for v in fila):
            res.filas_ignoradas += 1

    cerrar_sin_total()

    if res.controla_balance and not res.cuadra_debito_credito:
        res.errores.append(
            f"Débito total {res.total_debito} distinto de Crédito total {res.total_credito}"
        )
    return res
