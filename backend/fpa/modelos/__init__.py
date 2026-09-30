"""Importa todos los modelos para que Alembic y `Base.metadata` los conozcan."""

from fpa.modelos.base import Base
from fpa.modelos.identidad import Asignacion, Rol, Usuario
from fpa.modelos.organizacion import Hotel, Organizacion

__all__ = ["Asignacion", "Base", "Hotel", "Organizacion", "Rol", "Usuario"]
