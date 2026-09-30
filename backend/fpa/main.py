from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fpa.api import health
from fpa.api.v1 import catalogo, identidad, saldos
from fpa.config import settings


def crear_app() -> FastAPI:
    app = FastAPI(title=settings.app_nombre, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(identidad.router, prefix="/api/v1")
    app.include_router(catalogo.router, prefix="/api/v1")
    app.include_router(saldos.router, prefix="/api/v1")
    return app


app = crear_app()
