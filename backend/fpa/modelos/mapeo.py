"""Mapeo de cuentas locales a líneas del reporte, versionado por hotel.

Una `VersionMapeo` pasa por `borrador` (editable) -> `aprobada` (inmutable; una sola vigente por
hotel) -> `reemplazada` cuando se aprueba otra. Un borrador que se descarta queda como `descartada`.
Los vínculos (`MapeoLineaCuenta`) pertenecen a la versión y se anclan a una versión de estructura.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc

BORRADOR = "borrador"
APROBADA = "aprobada"
REEMPLAZADA = "reemplazada"
DESCARTADA = "descartada"


class VersionMapeo(Base):
    __tablename__ = "version_mapeo"
    __table_args__ = (
        UniqueConstraint("hotel_id", "numero"),
        # Una sola aprobada vigente y un solo borrador por hotel (defensa en la base de datos)
        Index(
            "uq_mapeo_aprobada_hotel",
            "hotel_id",
            unique=True,
            sqlite_where=text("estado = 'aprobada'"),
            postgresql_where=text("estado = 'aprobada'"),
        ),
        Index(
            "uq_mapeo_borrador_hotel",
            "hotel_id",
            unique=True,
            sqlite_where=text("estado = 'borrador'"),
            postgresql_where=text("estado = 'borrador'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)  # consecutivo por hotel
    version_estructura_id: Mapped[int] = mapped_column(ForeignKey("version_estructura_reporte.id"))
    estado: Mapped[str] = mapped_column(String(20), default=BORRADOR)
    origen: Mapped[str] = mapped_column(String(255))  # archivo de Excel o "copia de la versión N"
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    creada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    aprobada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    aprobada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MapeoLineaCuenta(Base):
    __tablename__ = "mapeo_linea_cuenta"
    __table_args__ = (UniqueConstraint("version_mapeo_id", "linea_id", "cuenta_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_mapeo_id: Mapped[int] = mapped_column(ForeignKey("version_mapeo.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("linea_reporte.id"))
    cuenta_codigo: Mapped[str] = mapped_column(String(40), index=True)
    signo: Mapped[int] = mapped_column(Integer)  # +1 o -1
    origen: Mapped[str] = mapped_column(String(10), default="excel")  # excel | manual
    # Anotación libre del vínculo (p. ej. «No se utiliza»): se ve en el desglose del reporte
    nota: Mapped[str | None] = mapped_column(String(160), nullable=True)


class CuentaExcluidaMapeo(Base):
    """Cuenta con movimientos que **a propósito** no entra a ninguna línea (con su motivo).

    Sin esto, el mapeo no se podría aprobar mientras exista una cuenta sin vínculo; así la
    decisión queda escrita, con quién la tomó y por qué.
    """

    __tablename__ = "cuenta_excluida_mapeo"
    __table_args__ = (UniqueConstraint("version_mapeo_id", "cuenta_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_mapeo_id: Mapped[int] = mapped_column(ForeignKey("version_mapeo.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    cuenta_codigo: Mapped[str] = mapped_column(String(40))
    motivo: Mapped[str] = mapped_column(String(500))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
