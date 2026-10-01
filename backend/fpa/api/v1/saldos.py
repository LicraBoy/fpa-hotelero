from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.repositorios.saldos import RepositorioSaldos

router = APIRouter(tags=["saldos"], responses=RESPUESTAS_HOTEL)


class SaldoSalida(BaseModel):
    cuenta_codigo: str
    suma_debito: Decimal
    suma_credito: Decimal
    neto: Decimal  # Débito − Crédito
    n_movimientos: int


@router.get("/hoteles/{hotel_id}/saldos", response_model=list[SaldoSalida])
def saldos_del_periodo(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.SALDOS_LEER))],
    periodo: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", description="AAAA-MM")],
    db: Session = Depends(get_db),
) -> list[SaldoSalida]:
    """Saldo de cada cuenta en el periodo, calculado desde la carga vigente."""
    return [
        SaldoSalida(
            cuenta_codigo=s.cuenta_codigo,
            suma_debito=s.suma_debito,
            suma_credito=s.suma_credito,
            neto=s.neto,
            n_movimientos=s.n_movimientos,
        )
        for s in RepositorioSaldos(db, contexto.hotel_id).del_periodo(periodo)
    ]
