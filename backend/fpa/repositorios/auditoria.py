from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.auditoria import EventoAuditoria


class RepositorioAuditoria:
    """Eventos de un hotel (siempre acotado por `hotel_id`)."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def listar(self, accion: str | None = None) -> list[EventoAuditoria]:
        consulta = select(EventoAuditoria).where(EventoAuditoria.hotel_id == self.hotel_id)
        if accion is not None:
            consulta = consulta.where(EventoAuditoria.accion == accion)
        return list(self._db.scalars(consulta.order_by(EventoAuditoria.id)))
