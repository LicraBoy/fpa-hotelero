"""Respuestas de error comunes, para que el OpenAPI describa lo que la API realmente devuelve."""

from typing import Any

RESPUESTAS_HOTEL: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin permiso para esta acción en el hotel"},
    404: {"description": "Hotel o recurso no encontrado (o sin acceso)"},
}

RESPUESTAS_REPORTE: dict[int | str, dict[str, Any]] = {
    **RESPUESTAS_HOTEL,
    409: {"description": "El Budget y el mapeo usan estructuras del reporte distintas"},
}
