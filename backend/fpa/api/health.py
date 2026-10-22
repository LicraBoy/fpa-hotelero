from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.db import get_db
from fpa.observabilidad.metricas import CONTENT_TYPE_LATEST, exponer_metricas

router = APIRouter(tags=["salud"])


@router.get("/health")
def health() -> dict[str, str]:
    """El proceso está vivo (no consulta la base de datos)."""
    return {"estado": "ok", "app": settings.app_nombre, "version": settings.app_version}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """La aplicación puede atender peticiones: responde si la base de datos contesta."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        # No se expone el detalle del error al cliente
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from None
    return {"estado": "listo"}


@router.get("/metrics", responses={200: {"content": {CONTENT_TYPE_LATEST: {}}}})
def metricas() -> Response:
    """Formato de texto de Prometheus (Fase 6.5). Sin autenticación: no trae datos de negocio,
    solo conteos/latencias de la propia API — igual que `/health`."""
    cuerpo, content_type = exponer_metricas()
    return Response(content=cuerpo, media_type=content_type)
