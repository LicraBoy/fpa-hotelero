"""Estructura del reporte Variance (secciones, líneas, orden y tipo), por hotel y versionada.

Una `VersionEstructuraReporte` es una foto de la estructura importada de un archivo. Solo una está
vigente por hotel; importar otra distinta deja la anterior como `reemplazada` (historial).
El mapeo a cuentas (2.3) y las reglas de suma (2.2) cuelgan de estas líneas.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc


class VersionEstructuraReporte(Base):
    __tablename__ = "version_estructura_reporte"
    __table_args__ = (
        Index(
            "uq_estructura_vigente_hotel",
            "hotel_id",
            unique=True,
            sqlite_where=text("estado = 'vigente'"),
            postgresql_where=text("estado = 'vigente'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    periodo_referencia: Mapped[str | None] = mapped_column(String(7), nullable=True)  # AAAA-MM
    estado: Mapped[str] = mapped_column(String(20), default="vigente")
    n_lineas: Mapped[int] = mapped_column(Integer)
    n_detalle: Mapped[int] = mapped_column(Integer)
    controles: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    reemplazada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LineaReporte(Base):
    __tablename__ = "linea_reporte"
    __table_args__ = (UniqueConstraint("version_id", "orden"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("version_estructura_reporte.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20))  # TipoLinea
    nivel: Mapped[int] = mapped_column(Integer)
    seccion_id: Mapped[int | None] = mapped_column(ForeignKey("linea_reporte.id"), nullable=True)
    # No es único: una misma cuenta corporativa aparece en varias líneas
    codigo_corporativo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    descripcion: Mapped[str] = mapped_column(String(300))
    # Provisional hasta que Contraloría confirme la clave natural de una línea
    clave: Mapped[str] = mapped_column(String(120))
    fila_origen: Mapped[int] = mapped_column(Integer)
