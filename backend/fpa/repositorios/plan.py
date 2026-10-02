"""Consultas de versiones del plan (Budget). **Todas** están acotadas a un hotel (aislamiento)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.modelos.plan import (
    VIGENTE,
    LineaPlan,
    LineaPlanMensual,
    ValorCapturado,
    VersionPlan,
)


class RepositorioPlan:
    """No existe forma de construirlo sin `hotel_id`: nada consulta datos de otro hotel."""

    def __init__(self, db: Session, hotel_id: int) -> None:
        self._db = db
        self.hotel_id = hotel_id

    def versiones(self, tipo: str | None = None) -> list[VersionPlan]:
        consulta = select(VersionPlan).where(VersionPlan.hotel_id == self.hotel_id)
        if tipo is not None:
            consulta = consulta.where(VersionPlan.tipo == tipo)
        return list(self._db.scalars(consulta.order_by(VersionPlan.tipo, VersionPlan.numero)))

    def obtener(self, version_id: int) -> VersionPlan | None:
        return self._db.scalar(
            select(VersionPlan).where(
                VersionPlan.id == version_id, VersionPlan.hotel_id == self.hotel_id
            )
        )

    def vigente(self, tipo: str, ano_fiscal: str) -> VersionPlan | None:
        return self._db.scalar(
            select(VersionPlan).where(
                VersionPlan.hotel_id == self.hotel_id,
                VersionPlan.tipo == tipo,
                VersionPlan.ano_fiscal == ano_fiscal,
                VersionPlan.estado == VIGENTE,
            )
        )

    def siguiente_numero(self, tipo: str) -> int:
        maximo = self._db.scalar(
            select(func.max(VersionPlan.numero)).where(
                VersionPlan.hotel_id == self.hotel_id, VersionPlan.tipo == tipo
            )
        )
        return (maximo or 0) + 1

    def lineas(self, version_id: int) -> list[LineaPlan]:
        return list(
            self._db.scalars(
                select(LineaPlan)
                .where(LineaPlan.version_plan_id == version_id, LineaPlan.hotel_id == self.hotel_id)
                .order_by(LineaPlan.linea_id)
            )
        )

    def mensuales(self, version_id: int) -> list[LineaPlanMensual]:
        return list(
            self._db.scalars(
                select(LineaPlanMensual)
                .where(
                    LineaPlanMensual.version_plan_id == version_id,
                    LineaPlanMensual.hotel_id == self.hotel_id,
                )
                .order_by(LineaPlanMensual.periodo, LineaPlanMensual.linea_id)
            )
        )

    def capturados(self, version_estructura_id: int, periodos: list[str]) -> list[ValorCapturado]:
        return list(
            self._db.scalars(
                select(ValorCapturado)
                .where(
                    ValorCapturado.hotel_id == self.hotel_id,
                    ValorCapturado.version_estructura_id == version_estructura_id,
                    ValorCapturado.periodo.in_(periodos),
                )
                .order_by(ValorCapturado.linea_id)
            )
        )
