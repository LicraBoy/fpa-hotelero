"""Bitácora de auditoría: solo se inserta, nunca se modifica ni se borra.

Hoy la regla se hace cumplir en la aplicación (eventos de SQLAlchemy). Con PostgreSQL se
reforzará quitando UPDATE/DELETE al usuario de la aplicación y encadenando hashes
(Arquitectura §8.8, Fase 5.5).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from fpa.modelos.base import Base, ahora_utc


class EventoAuditoria(Base):
    __tablename__ = "evento_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(ForeignKey("organizacion.id"), index=True)
    hotel_id: Mapped[int | None] = mapped_column(ForeignKey("hotel.id"), nullable=True, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str] = mapped_column(String(60))
    entidad_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class AuditoriaInmutable(RuntimeError):
    """Se intentó modificar o borrar un evento de auditoría."""


@event.listens_for(EventoAuditoria, "before_update")
def _prohibir_update(mapper: Mapper[Any], connection: Connection, target: EventoAuditoria) -> None:
    raise AuditoriaInmutable("Los eventos de auditoría no se pueden modificar")


@event.listens_for(EventoAuditoria, "before_delete")
def _prohibir_delete(mapper: Mapper[Any], connection: Connection, target: EventoAuditoria) -> None:
    raise AuditoriaInmutable("Los eventos de auditoría no se pueden borrar")
