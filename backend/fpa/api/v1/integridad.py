"""Verificación de la cadena de hashes de la bitácora (Fase 5.5). Solo lectura."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.servicios.cadena_auditoria import verificar

router = APIRouter(tags=["auditoria"], responses=RESPUESTAS_HOTEL)


class IntegridadSalida(BaseModel):
    integra: bool
    eventos: int
    # Anótalo aparte (p. ej. en el acta del cierre): permite notar que se borraron los últimos
    ultimo_hash: str
    primer_alterado_id: int | None
    motivo: str | None


@router.get("/hoteles/{hotel_id}/auditoria/verificar", response_model=IntegridadSalida)
def verificar_cadena(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.AUDITORIA_LEER))],
    db: Session = Depends(get_db),
) -> IntegridadSalida:
    """Recorre la bitácora de toda la organización (la cadena es una por organización)."""
    r = verificar(db, contexto.organizacion_id)
    return IntegridadSalida(
        integra=r.integra,
        eventos=r.eventos,
        ultimo_hash=r.ultimo_hash,
        primer_alterado_id=r.primer_alterado_id,
        motivo=r.motivo,
    )
