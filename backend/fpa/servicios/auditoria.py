from typing import Any

from sqlalchemy.orm import Session

from fpa.modelos.auditoria import EventoAuditoria


def auditar(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int | None,
    usuario_id: int | None,
    accion: str,
    entidad: str,
    entidad_id: int | None = None,
    detalle: dict[str, Any] | None = None,
) -> EventoAuditoria:
    """Agrega un evento a la bitácora (dentro de la transacción del llamador)."""
    evento = EventoAuditoria(
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle=detalle,
    )
    db.add(evento)
    db.flush()
    return evento
