"""Invalida la caché de reportes de un hotel cuando se escribe algo en su API.

Cualquier petición que modifica (POST, PUT, PATCH, DELETE) y termina bien (< 400) sube la
generación de ese hotel; ya se hizo su `commit`, así que lo siguiente que se lea es lo nuevo. Una
petición que falla (400 en adelante) no cambió nada y no invalida. Como vale para toda ruta bajo
`/api/v1/hoteles/{id}/`, una ruta nueva que escriba queda cubierta sin acordarse de invalidar.
"""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fpa.servicios.reportes import cache_variance

_RUTA_HOTEL = re.compile(r"^/api/v1/hoteles/(\d{1,10})/")
_ESCRITURAS = {"POST", "PUT", "PATCH", "DELETE"}


class InvalidarCacheTrasEscritura(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        respuesta = await call_next(request)
        if request.method in _ESCRITURAS and respuesta.status_code < 400:
            m = _RUTA_HOTEL.match(request.url.path)
            if m:
                cache_variance.invalidar_hotel(int(m.group(1)))
        return respuesta
