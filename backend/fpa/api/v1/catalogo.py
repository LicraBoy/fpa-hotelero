from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import Permiso
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.servicios.catalogo import NodoCatalogo, construir_arbol

router = APIRouter(tags=["catalogo"])


class NodoSalida(BaseModel):
    codigo: str
    descripcion: str | None
    clase: str
    nivel: int | None
    con_movimientos: bool
    es_titulo: bool
    sin_jerarquia: bool
    hijos: list["NodoSalida"]


def _a_salida(nodo: NodoCatalogo) -> NodoSalida:
    return NodoSalida(
        codigo=nodo.codigo,
        descripcion=nodo.descripcion,
        clase=nodo.clase,
        nivel=nodo.nivel,
        con_movimientos=nodo.con_movimientos,
        es_titulo=nodo.es_titulo,
        sin_jerarquia=nodo.sin_jerarquia,
        hijos=[_a_salida(h) for h in nodo.hijos],
    )


@router.get("/hoteles/{hotel_id}/catalogo/arbol", response_model=list[NodoSalida])
def arbol_del_catalogo(
    contexto: Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.CATALOGO_LEER))],
    db: Session = Depends(get_db),
) -> list[NodoSalida]:
    """Árbol de cuentas locales del hotel (títulos de la jerarquía y cuentas con movimientos)."""
    cuentas = RepositorioCatalogo(db, contexto.hotel_id).todas()
    return [_a_salida(n) for n in construir_arbol(cuentas)]
