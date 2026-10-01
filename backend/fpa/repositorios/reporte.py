"""Consultas de la estructura del reporte. **Todas** están acotadas a un hotel (aislamiento)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.reporte import LineaReporte, ReglaSumaLinea, VersionEstructuraReporte


class RepositorioReporte:
    """No existe forma de construirlo sin `hotel_id`: nada consulta datos de otro hotel."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def versiones(self) -> list[VersionEstructuraReporte]:
        return list(
            self._db.scalars(
                select(VersionEstructuraReporte)
                .where(VersionEstructuraReporte.hotel_id == self.hotel_id)
                .order_by(VersionEstructuraReporte.id)
            )
        )

    def vigente(self) -> VersionEstructuraReporte | None:
        return self._db.scalar(
            select(VersionEstructuraReporte).where(
                VersionEstructuraReporte.hotel_id == self.hotel_id,
                VersionEstructuraReporte.estado == "vigente",
            )
        )

    def obtener(self, version_id: int) -> VersionEstructuraReporte | None:
        return self._db.scalar(
            select(VersionEstructuraReporte).where(
                VersionEstructuraReporte.id == version_id,
                VersionEstructuraReporte.hotel_id == self.hotel_id,
            )
        )

    def lineas(self, version_id: int) -> list[LineaReporte]:
        return list(
            self._db.scalars(
                select(LineaReporte)
                .where(
                    LineaReporte.version_id == version_id, LineaReporte.hotel_id == self.hotel_id
                )
                .order_by(LineaReporte.orden)
            )
        )

    def reglas(self, version_id: int) -> list[ReglaSumaLinea]:
        return list(
            self._db.scalars(
                select(ReglaSumaLinea)
                .where(
                    ReglaSumaLinea.version_id == version_id,
                    ReglaSumaLinea.hotel_id == self.hotel_id,
                )
                .order_by(ReglaSumaLinea.linea_id, ReglaSumaLinea.id)
            )
        )
