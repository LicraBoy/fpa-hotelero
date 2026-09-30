from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado, principal_actual
from fpa.identidad.permisos import Permiso
from fpa.identidad.principal import Principal
from fpa.modelos.organizacion import Hotel

router = APIRouter(tags=["identidad"])


class YoSalida(BaseModel):
    usuario_id: int
    email: str
    organizacion_id: int
    roles_por_hotel: dict[int, str]


class HotelSalida(BaseModel):
    id: int
    codigo: str
    nombre: str
    rol: str


@router.get("/yo", response_model=YoSalida)
def yo(principal: Annotated[Principal, Depends(principal_actual)]) -> YoSalida:
    return YoSalida(
        usuario_id=principal.usuario_id,
        email=principal.email,
        organizacion_id=principal.organizacion_id,
        roles_por_hotel=principal.roles_por_hotel,
    )


@router.get("/hoteles", response_model=list[HotelSalida])
def mis_hoteles(
    principal: Annotated[Principal, Depends(principal_actual)],
    db: Session = Depends(get_db),
) -> list[HotelSalida]:
    """Solo los hoteles a los que el usuario tiene acceso."""
    if not principal.roles_por_hotel:
        return []
    hoteles = db.scalars(
        select(Hotel)
        .where(
            Hotel.id.in_(principal.roles_por_hotel),
            Hotel.organizacion_id == principal.organizacion_id,
        )
        .order_by(Hotel.nombre)
    ).all()
    return [
        HotelSalida(id=h.id, codigo=h.codigo, nombre=h.nombre, rol=principal.roles_por_hotel[h.id])
        for h in hoteles
    ]


@router.get("/hoteles/{hotel_id}", response_model=HotelSalida)
def detalle_hotel(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.HOTEL_LEER))],
    db: Session = Depends(get_db),
) -> HotelSalida:
    hotel = db.scalar(
        select(Hotel).where(
            Hotel.id == contexto.hotel_id, Hotel.organizacion_id == contexto.organizacion_id
        )
    )
    if hotel is None:  # no debería pasar: la asignación ya lo garantiza
        raise HTTPException(status_code=404, detail="Hotel no encontrado")
    return HotelSalida(
        id=hotel.id,
        codigo=hotel.codigo,
        nombre=hotel.nombre,
        rol=contexto.principal.roles_por_hotel[hotel.id],
    )
