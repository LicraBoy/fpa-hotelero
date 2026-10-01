"""Año fiscal y periodos acumulados (YTD).

El año fiscal de Torres empieza en julio (`MES_INICIO_POR_DEFECTO = 7`) **[POR VALIDAR con
Contraloría]**: el YTD de agosto 2026 del Variance suma julio y agosto. Es un parámetro, no una
constante escondida: un año fiscal calendario es `mes_inicio=1`.
"""

from __future__ import annotations

import re

MES_INICIO_POR_DEFECTO = 7
_RE_PERIODO = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _partes(periodo: str) -> tuple[int, int]:
    m = _RE_PERIODO.match(periodo)
    if m is None:
        raise ValueError(f"Periodo inválido {periodo!r}: debe ser AAAA-MM")
    return int(m.group(1)), int(m.group(2))


def etiqueta_ano_fiscal(periodo: str, mes_inicio: int = MES_INICIO_POR_DEFECTO) -> str:
    """`2026-08` -> `2026/27` (julio-junio) o `2026` (si el año fiscal es el calendario)."""
    _validar_mes_inicio(mes_inicio)
    anio, mes = _partes(periodo)
    if mes_inicio == 1:
        return str(anio)
    inicio = anio if mes >= mes_inicio else anio - 1
    return f"{inicio}/{(inicio + 1) % 100:02d}"


def _validar_mes_inicio(mes_inicio: int) -> None:
    if not 1 <= mes_inicio <= 12:
        raise ValueError("El mes de inicio del año fiscal debe estar entre 1 y 12")


def inicio_ano_fiscal(periodo: str, mes_inicio: int = MES_INICIO_POR_DEFECTO) -> str:
    """Primer mes del año fiscal que contiene a `periodo`: `2026-08` -> `2026-07`."""
    _validar_mes_inicio(mes_inicio)
    anio, mes = _partes(periodo)
    inicio = anio if mes >= mes_inicio else anio - 1
    return f"{inicio:04d}-{mes_inicio:02d}"


def periodos_ytd(periodo: str, mes_inicio: int = MES_INICIO_POR_DEFECTO) -> list[str]:
    """Meses del año fiscal desde su inicio hasta `periodo` inclusive, en orden.

    `2026-08` -> [`2026-07`, `2026-08`]; `2027-01` -> julio a enero; `2026-07` -> [`2026-07`].
    """
    anio, mes = _partes(inicio_ano_fiscal(periodo, mes_inicio))
    _, mes_corte = _partes(periodo)
    n = (mes_corte - mes) % 12 + 1
    salida: list[str] = []
    for _ in range(n):
        salida.append(f"{anio:04d}-{mes:02d}")
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return salida


def periodos_del_ano_fiscal(periodo: str, mes_inicio: int = MES_INICIO_POR_DEFECTO) -> list[str]:
    """Los 12 meses del año fiscal que contiene a `periodo`."""
    anio, mes = _partes(inicio_ano_fiscal(periodo, mes_inicio))
    salida: list[str] = []
    for _ in range(12):
        salida.append(f"{anio:04d}-{mes:02d}")
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return salida
