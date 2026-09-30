"""Importa todos los modelos para que Alembic y `Base.metadata` los conozcan."""

from fpa.modelos.base import Base
from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento
from fpa.modelos.identidad import Asignacion, Rol, Usuario
from fpa.modelos.organizacion import Hotel, Organizacion

__all__ = [
    "Asignacion",
    "Base",
    "CargaArchivo",
    "EstadoCarga",
    "Hotel",
    "Movimiento",
    "Organizacion",
    "Rol",
    "Usuario",
]
