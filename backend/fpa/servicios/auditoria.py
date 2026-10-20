from typing import Any

from sqlalchemy.orm import Session

from fpa.modelos.auditoria import EventoAuditoria
from fpa.modelos.base import ahora_utc
from fpa.servicios.cadena_auditoria import hash_de, ultimo_hash


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
    """Agrega un evento a la bitácora (dentro de la transacción del llamador).

    Lo encadena con el anterior de la organización. Se escribe lo pendiente antes de buscar el
    anterior, para que dos eventos de la misma transacción no se encadenen al mismo.
    """
    db.flush()
    previo = ultimo_hash(db, organizacion_id)
    evento = EventoAuditoria(
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle=detalle,
        creado_en=ahora_utc(),
        hash_previo=previo,
    )
    evento.hash = hash_de(evento, previo)
    db.add(evento)
    db.flush()
    return evento
