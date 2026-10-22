"""Middleware de `request_id` + métricas por petición (Fase 6.5).

Cada petición recibe un id (el que traiga `X-Request-Id`, o uno nuevo), que viaja en la respuesta
y en cada línea de log mientras se atiende esa petición (ver `fpa/observabilidad/registro.py`).
De paso cuenta peticiones y mide su duración para Prometheus (`fpa/observabilidad/metricas.py`).
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fpa.observabilidad.metricas import PETICIONES_DURACION_S, PETICIONES_TOTAL
from fpa.observabilidad.registro import fijar_id_de_peticion

log = logging.getLogger(__name__)

CABECERA_ID = "X-Request-Id"


def _ruta_para_metricas(request: Request) -> str:
    """La ruta con plantilla (`/api/v1/cuentas/{codigo}`), no la URL real, para no explotar la
    cardinalidad de la métrica con un valor distinto por cada id real."""
    ruta = request.scope.get("route")
    return getattr(ruta, "path", request.url.path)


class IdDePeticion(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        id_peticion = request.headers.get(CABECERA_ID) or uuid.uuid4().hex
        fijar_id_de_peticion(id_peticion)
        inicio = time.perf_counter()
        ruta = _ruta_para_metricas(request)
        try:
            respuesta = await call_next(request)
        except Exception:
            duracion = time.perf_counter() - inicio
            PETICIONES_TOTAL.labels(method=request.method, ruta=ruta, estado="500").inc()
            PETICIONES_DURACION_S.labels(method=request.method, ruta=ruta).observe(duracion)
            log.exception("Petición sin manejar: %s %s", request.method, request.url.path)
            raise
        finally:
            fijar_id_de_peticion(None)
        duracion = time.perf_counter() - inicio
        PETICIONES_TOTAL.labels(
            method=request.method, ruta=ruta, estado=str(respuesta.status_code)
        ).inc()
        PETICIONES_DURACION_S.labels(method=request.method, ruta=ruta).observe(duracion)
        respuesta.headers[CABECERA_ID] = id_peticion
        return respuesta
