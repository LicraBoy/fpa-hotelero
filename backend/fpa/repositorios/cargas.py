"""Consultas de cargas y movimientos. **Todas** están acotadas a un hotel (aislamiento)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento


class RepositorioCargas:
    """No existe forma de construirlo sin `hotel_id`: nada consulta datos de otro hotel."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def listar(self, estado: EstadoCarga | None = None) -> list[CargaArchivo]:
        consulta = select(CargaArchivo).where(CargaArchivo.hotel_id == self.hotel_id)
        if estado is not None:
            consulta = consulta.where(CargaArchivo.estado == estado.value)
        return list(self._db.scalars(consulta.order_by(CargaArchivo.periodo, CargaArchivo.id)))

    def obtener(self, carga_id: int) -> CargaArchivo | None:
        return self._db.scalar(
            select(CargaArchivo).where(
                CargaArchivo.id == carga_id, CargaArchivo.hotel_id == self.hotel_id
            )
        )

    def vigente_de_periodo(self, periodo: str) -> CargaArchivo | None:
        return self._db.scalar(
            select(CargaArchivo).where(
                CargaArchivo.hotel_id == self.hotel_id,
                CargaArchivo.periodo == periodo,
                CargaArchivo.estado == EstadoCarga.VIGENTE.value,
            )
        )

    def movimientos_de_carga(self, carga_id: int) -> list[Movimiento]:
        return list(
            self._db.scalars(
                select(Movimiento)
                .where(Movimiento.carga_id == carga_id, Movimiento.hotel_id == self.hotel_id)
                .order_by(Movimiento.id)
            )
        )

    def movimientos_vigentes(self, periodo: str) -> list[Movimiento]:
        """Movimientos que cuentan para los cálculos: solo los de la carga vigente del periodo."""
        return list(
            self._db.scalars(
                select(Movimiento)
                .join(CargaArchivo, CargaArchivo.id == Movimiento.carga_id)
                .where(
                    Movimiento.hotel_id == self.hotel_id,
                    Movimiento.periodo == periodo,
                    CargaArchivo.estado == EstadoCarga.VIGENTE.value,
                )
                .order_by(Movimiento.id)
            )
        )
