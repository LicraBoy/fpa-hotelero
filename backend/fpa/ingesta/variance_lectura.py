"""Lectura del Excel del Variance en cualquiera de sus formatos (Vallarta o Mazatlán)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fpa.ingesta.formato_variance import Formato, detectar_formato
from fpa.ingesta.variance_estructura import (
    ResultadoEstructura,
    leer_filas_hoja,
    leer_variance_estructura_filas,
)
from fpa.ingesta.variance_mapeo import ResultadoMapeo, leer_variance_mapeo_filas
from fpa.ingesta.variance_mzt import (
    leer_estructura_mzt,
    leer_hojas_mzt,
    leer_mapeo_mzt,
    leer_reglas_mzt,
)
from fpa.ingesta.variance_reglas import ResultadoReglas, leer_variance_reglas_filas


@dataclass
class LecturaVariance:
    formato: Formato
    estructura: ResultadoEstructura
    reglas: ResultadoReglas
    mapeo: ResultadoMapeo


def leer_variance(ruta: str | Path) -> LecturaVariance:
    """Estructura, reglas de suma y mapeo del libro, según su formato. `ValueError` si no sirve."""
    perfil = detectar_formato(ruta)
    if perfil.formato is Formato.MZT:
        hojas = leer_hojas_mzt(ruta)
        estructura = leer_estructura_mzt(hojas)
        return LecturaVariance(
            Formato.MZT,
            estructura,
            leer_reglas_mzt(hojas, estructura),
            leer_mapeo_mzt(hojas, estructura),
        )
    filas = leer_filas_hoja(ruta)
    estructura = leer_variance_estructura_filas(filas)
    return LecturaVariance(
        Formato.VT,
        estructura,
        leer_variance_reglas_filas(filas, estructura),
        leer_variance_mapeo_filas(filas, estructura),
    )
