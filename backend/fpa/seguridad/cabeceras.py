"""Cabeceras de seguridad de la API.

La API solo devuelve datos (JSON, y más adelante archivos de descarga): nunca debe ejecutarse ni
incrustarse en una página. Por eso su CSP es la más estricta posible, y como lo que sirve son cifras
financieras, no se guarda en cachés compartidas ni del navegador.

El frontend se sirve aparte; su política está en `frontend/vite.config.ts` y en
`docs/adr/0004-seguridad-del-frontend.md` (para el proxy de producción).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CSP_API = "default-src 'none'; frame-ancestors 'none'"

CABECERAS_API: dict[str, str] = {
    "Content-Security-Policy": CSP_API,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class CabecerasDeSeguridad(BaseHTTPMiddleware):
    """Añade las cabeceras a toda respuesta de `/api` (la documentación en `/docs` queda fuera)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        respuesta = await call_next(request)
        if request.url.path.startswith("/api/"):
            for nombre, valor in CABECERAS_API.items():
                respuesta.headers[nombre] = valor
            # Cifras financieras: ni el navegador ni un proxy deben guardarlas.
            respuesta.headers.setdefault("Cache-Control", "no-store")
        return respuesta
