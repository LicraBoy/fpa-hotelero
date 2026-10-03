"""Dónde están los Excel reales de Torres (nunca dentro del repositorio).

Carpeta: la variable de entorno `FPA_DATOS_REALES` o, por omisión,
`~/Desktop/PLATAFORMA FP&A E INTELIGENCIA HOTELERA`. Las pruebas y la demostración que
los usan se saltan si el archivo no está.
"""

from __future__ import annotations

import os
from pathlib import Path


def carpeta_datos_reales() -> Path:
    return Path(
        os.environ.get(
            "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
        )
    )


def archivo_real(nombre: str) -> Path:
    """Ruta del archivo real (puede no existir: quien lo usa decide si se salta)."""
    return carpeta_datos_reales() / nombre
