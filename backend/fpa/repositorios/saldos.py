from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.saldos import SaldoMensualCuenta


class RepositorioSaldos:
    """Saldos de un hotel (siempre acotado por `hotel_id`)."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def del_periodo(self, periodo: str) -> list[SaldoMensualCuenta]:
        return list(
            self._db.scalars(
                select(SaldoMensualCuenta)
                .where(
                    SaldoMensualCuenta.hotel_id == self.hotel_id,
                    SaldoMensualCuenta.periodo == periodo,
                )
                .order_by(SaldoMensualCuenta.cuenta_codigo)
            )
        )

    def periodos(self) -> list[str]:
        return sorted(
            set(
                self._db.scalars(
                    select(SaldoMensualCuenta.periodo).where(
                        SaldoMensualCuenta.hotel_id == self.hotel_id
                    )
                )
            )
        )
