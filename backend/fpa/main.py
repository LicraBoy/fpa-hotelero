from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from fpa.api import health
from fpa.api.v1 import (
    auth,
    budget,
    cargas,
    catalogo,
    drilldown,
    identidad,
    mapeo,
    saldos,
    usuarios,
    variance,
)
from fpa.config import settings
from fpa.seguridad.cabeceras import CabecerasDeSeguridad
from fpa.seguridad.invalidar_cache import InvalidarCacheTrasEscritura
from fpa.seguridad.origen import ProtegerOrigen


def _openapi_con_errores_de_negocio(app: FastAPI) -> dict[str, Any]:
    """Un 422 puede traer la lista de FastAPI o un texto de negocio: el contrato admite ambos."""
    if app.openapi_schema is None:
        esquema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        detalle = esquema["components"]["schemas"]["HTTPValidationError"]["properties"]["detail"]
        esquema["components"]["schemas"]["HTTPValidationError"]["properties"]["detail"] = {
            "anyOf": [detalle, {"type": "string"}],
            "title": "Detail",
        }
        app.openapi_schema = esquema
    return app.openapi_schema


def crear_app() -> FastAPI:
    app = FastAPI(title=settings.app_nombre, version=settings.app_version)
    app.openapi = lambda: _openapi_con_errores_de_negocio(app)  # type: ignore[method-assign]
    app.add_middleware(InvalidarCacheTrasEscritura)
    app.add_middleware(CabecerasDeSeguridad)
    app.add_middleware(ProtegerOrigen)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(identidad.router, prefix="/api/v1")
    app.include_router(usuarios.router, prefix="/api/v1")
    app.include_router(catalogo.router, prefix="/api/v1")
    app.include_router(saldos.router, prefix="/api/v1")
    app.include_router(cargas.router, prefix="/api/v1")
    app.include_router(mapeo.router, prefix="/api/v1")
    app.include_router(budget.router, prefix="/api/v1")
    app.include_router(variance.router, prefix="/api/v1")
    app.include_router(drilldown.router, prefix="/api/v1")
    return app


app = crear_app()
