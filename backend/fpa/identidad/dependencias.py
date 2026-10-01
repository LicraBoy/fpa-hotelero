"""Dependencias de FastAPI para autenticar y autorizar.

Reglas (ADR 0003):
- Sin sesión válida -> 401.
- Hotel al que el usuario no tiene acceso -> 404 (no se revela si existe).
- Hotel propio pero sin el permiso -> 403.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from fpa.db import get_db
from fpa.identidad.permisos import Permiso
from fpa.identidad.principal import Principal
from fpa.identidad.proveedor import ProveedorIdentidad, crear_proveedor


def obtener_proveedor() -> ProveedorIdentidad:
    """Punto único para cambiar de proveedor (las pruebas lo sustituyen)."""
    return crear_proveedor()


def principal_actual(
    request: Request,
    db: Session = Depends(get_db),
    proveedor: ProveedorIdentidad = Depends(obtener_proveedor),
) -> Principal:
    principal = proveedor.autenticar(request, db)
    if principal is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return principal


@dataclass(frozen=True)
class ContextoHotel:
    """Petición ya autorizada sobre un hotel concreto."""

    principal: Principal
    hotel_id: int

    @property
    def organizacion_id(self) -> int:
        return self.principal.organizacion_id


def hotel_autorizado(permiso: Permiso) -> Callable[..., ContextoHotel]:
    """Fábrica de dependencia: exige acceso al hotel de la ruta y un permiso en él."""

    def dependencia(
        hotel_id: Annotated[int, Path(ge=1, le=2_147_483_647)],
        principal: Principal = Depends(principal_actual),
    ) -> ContextoHotel:
        if not principal.tiene_acceso_a(hotel_id):
            raise HTTPException(status_code=404, detail="Hotel no encontrado")
        if not principal.puede(hotel_id, permiso):
            raise HTTPException(status_code=403, detail="Sin permiso para esta acción")
        return ContextoHotel(principal=principal, hotel_id=hotel_id)

    return dependencia
