"""Defensa contra CSRF para las peticiones que llevan la cookie de sesión.

La cookie ya es `SameSite=Strict`; esta comprobación es la segunda capa: una petición que **cambia
datos** y trae la cookie de sesión debe venir de uno de los orígenes del frontend
(`settings.cors_origins`). Sin cabecera `Origin` (clientes que no son un navegador, pruebas) se deja
pasar, porque un navegador siempre la envía en peticiones que modifican.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fpa.config import settings

METODOS_QUE_MODIFICAN = {"POST", "PUT", "PATCH", "DELETE"}


class ProtegerOrigen(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            request.method in METODOS_QUE_MODIFICAN
            and request.url.path.startswith("/api/")
            and settings.cookie_nombre in request.cookies
        ):
            origen = request.headers.get("origin")
            if origen is not None and origen not in settings.cors_origins:
                return JSONResponse(
                    status_code=403, content={"detail": "Origen no permitido para esta acción"}
                )
        return await call_next(request)
