"""Saldo mensual por cuenta: dato **derivado** de los movimientos de la carga vigente.

No es fuente de verdad: se puede borrar y recalcular siempre (`recalcular_saldos`). Sirve para que
los reportes lean un agregado pequeño en vez de miles de movimientos. Resultado de la cuenta =
Débito − Crédito (la regla del Excel actual).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc
from fpa.modelos.tipos import Dinero


class SaldoMensualCuenta(Base):
    __tablename__ = "saldo_mensual_cuenta"
    __table_args__ = (
        UniqueConstraint("hotel_id", "periodo", "cuenta_codigo"),
        Index("ix_saldo_hotel_periodo", "hotel_id", "periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"))
    periodo: Mapped[str] = mapped_column(String(7))
    cuenta_codigo: Mapped[str] = mapped_column(String(40))
    suma_debito: Mapped[Decimal] = mapped_column(Dinero)
    suma_credito: Mapped[Decimal] = mapped_column(Dinero)
    n_movimientos: Mapped[int] = mapped_column(Integer)
    # Carga vigente de la que se calculó
    carga_id: Mapped[int] = mapped_column(ForeignKey("carga_archivo.id"))
    calculado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    @property
    def neto(self) -> Decimal:
        """Resultado = Débito − Crédito."""
        return self.suma_debito - self.suma_credito
