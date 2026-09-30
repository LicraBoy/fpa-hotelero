"""Conversiones comunes a todos los lectores de Excel."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fpa.ingesta.contrato import CENTAVO

_RE_FECHA = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\s*$")


def a_dinero(valor: object) -> Decimal | None:
    """Número o texto con comas (ej. '16,189.85') -> Decimal; vacío -> None."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        raise ValueError(f"monto inválido: {valor!r}")
    if isinstance(valor, (int, float)):
        return Decimal(str(valor)).quantize(CENTAVO)
    texto = str(valor).strip().replace(",", "").replace("$", "")
    if texto == "":
        return None
    try:
        return Decimal(texto).quantize(CENTAVO)
    except InvalidOperation:
        raise ValueError(f"monto inválido: {valor!r}") from None


def a_decimal_exacto(valor: object) -> Decimal | None:
    """Cantidades y costos unitarios: conserva todos los decimales (no redondea a centavos)."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        raise ValueError(f"número inválido: {valor!r}")
    texto = str(valor).strip().replace(",", "")
    if texto == "":
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"número inválido: {valor!r}") from None


def a_fecha(valor: object) -> date | None:
    """Fecha de Excel (datetime) o texto dd/mm/aaaa -> date; si no es una fecha, None."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        m = _RE_FECHA.match(valor)
        if m:
            dia, mes, anio = (int(x) for x in m.groups())
            try:
                return date(anio, mes, dia)
            except ValueError:
                return None
    return None


def a_texto(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None
