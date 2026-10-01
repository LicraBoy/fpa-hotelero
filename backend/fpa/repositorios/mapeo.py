"""Consultas del mapeo. **Todas** están acotadas a un hotel (aislamiento)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.modelos.mapeo import APROBADA, BORRADOR, MapeoLineaCuenta, VersionMapeo


class RepositorioMapeo:
    """No existe forma de construirlo sin `hotel_id`: nada consulta datos de otro hotel."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def versiones(self) -> list[VersionMapeo]:
        return list(
            self._db.scalars(
                select(VersionMapeo)
                .where(VersionMapeo.hotel_id == self.hotel_id)
                .order_by(VersionMapeo.numero)
            )
        )

    def obtener(self, version_id: int) -> VersionMapeo | None:
        return self._db.scalar(
            select(VersionMapeo).where(
                VersionMapeo.id == version_id, VersionMapeo.hotel_id == self.hotel_id
            )
        )

    def _por_estado(self, estado: str) -> VersionMapeo | None:
        return self._db.scalar(
            select(VersionMapeo).where(
                VersionMapeo.hotel_id == self.hotel_id, VersionMapeo.estado == estado
            )
        )

    def aprobada(self) -> VersionMapeo | None:
        return self._por_estado(APROBADA)

    def borrador(self) -> VersionMapeo | None:
        return self._por_estado(BORRADOR)

    def siguiente_numero(self) -> int:
        maximo = self._db.scalar(
            select(func.max(VersionMapeo.numero)).where(VersionMapeo.hotel_id == self.hotel_id)
        )
        return (maximo or 0) + 1

    def vinculos(self, version_id: int) -> list[MapeoLineaCuenta]:
        return list(
            self._db.scalars(
                select(MapeoLineaCuenta)
                .where(
                    MapeoLineaCuenta.version_mapeo_id == version_id,
                    MapeoLineaCuenta.hotel_id == self.hotel_id,
                )
                .order_by(MapeoLineaCuenta.linea_id, MapeoLineaCuenta.cuenta_codigo)
            )
        )
