from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.catalogo import CuentaLocal


class RepositorioCatalogo:
    """Cuentas de un hotel (siempre acotado por `hotel_id`)."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def todas(self) -> list[CuentaLocal]:
        return list(
            self._db.scalars(
                select(CuentaLocal)
                .where(CuentaLocal.hotel_id == self.hotel_id)
                .order_by(CuentaLocal.codigo)
            )
        )

    def por_codigo(self) -> dict[str, CuentaLocal]:
        return {c.codigo: c for c in self.todas()}

    def codigos_con_movimientos(self) -> set[str]:
        return {c.codigo for c in self.todas() if c.con_movimientos}

    def codigos_oficiales(self) -> set[str]:
        """Cuentas del catálogo oficial (sin los títulos de la jerarquía)."""
        return {c.codigo for c in self.todas() if c.en_catalogo_oficial and c.tipo is not None}

    def codigos_inactivos(self) -> set[str]:
        return {
            c.codigo
            for c in self.todas()
            if c.en_catalogo_oficial and c.tipo is not None and not c.activa
        }
