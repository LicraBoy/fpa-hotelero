"""Comentarios que explican una variación (Blueprint §17, Fase 5.3).

Un comentario es por **línea + periodo + bloque** (mes o acumulado). El primero del hilo
(`padre_id` vacío) lleva el responsable y el estatus; las respuestas solo traen texto. Cada
versión del texto queda en `ComentarioRevision` (solo se inserta), y los adjuntos se guardan en
disco, no en la base.

La línea se guarda por su id en la estructura vigente al comentar, más su descripción como foto:
si algún día se importa otra estructura, el comentario se sigue leyendo aunque la línea cambie.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc

ESTATUS_COMENTARIO = ("pendiente", "explicado", "aprobado")


class ComentarioLinea(Base):
    __tablename__ = "comentario_linea"
    __table_args__ = (Index("ix_comentario_hotel_periodo", "hotel_id", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("linea_reporte.id"))
    linea_descripcion: Mapped[str] = mapped_column(String(300))
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    bloque: Mapped[str] = mapped_column(String(4))  # mes | ytd
    padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("comentario_linea.id"), nullable=True, index=True
    )
    texto: Mapped[str] = mapped_column(Text)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    # Solo en el primero del hilo
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    estatus: Mapped[str | None] = mapped_column(String(12), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class ComentarioRevision(Base):
    """Cada texto que tuvo un comentario (la primera fila es el original). Solo se inserta."""

    __tablename__ = "comentario_revision"

    id: Mapped[int] = mapped_column(primary_key=True)
    comentario_id: Mapped[int] = mapped_column(ForeignKey("comentario_linea.id"), index=True)
    texto: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class AdjuntoComentario(Base):
    """Evidencia de un comentario (PDF, imagen o Excel). El archivo vive en `storage/adjuntos/`."""

    __tablename__ = "adjunto_comentario"

    id: Mapped[int] = mapped_column(primary_key=True)
    comentario_id: Mapped[int] = mapped_column(ForeignKey("comentario_linea.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    extension: Mapped[str] = mapped_column(String(8))
    sha256: Mapped[str] = mapped_column(String(64))
    tamano: Mapped[int] = mapped_column(Integer)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
