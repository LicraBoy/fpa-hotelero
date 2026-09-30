"""Importa todos los modelos para que Alembic y `Base.metadata` los conozcan."""

from fpa.modelos.auditoria import EventoAuditoria
from fpa.modelos.base import Base
from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento
from fpa.modelos.catalogo import CuentaLocal
from fpa.modelos.identidad import Asignacion, Rol, Usuario
from fpa.modelos.organizacion import Hotel, Organizacion
from fpa.modelos.saldos import SaldoMensualCuenta

__all__ = [
    "Asignacion",
    "Base",
    "CargaArchivo",
    "CuentaLocal",
    "EstadoCarga",
    "EventoAuditoria",
    "Hotel",
    "Movimiento",
    "Organizacion",
    "Rol",
    "SaldoMensualCuenta",
    "Usuario",
]
