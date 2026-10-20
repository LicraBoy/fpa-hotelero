"""Importa todos los modelos para que Alembic y `Base.metadata` los conozcan."""

from fpa.modelos.auditoria import EventoAuditoria
from fpa.modelos.base import Base
from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento
from fpa.modelos.catalogo import CuentaLocal
from fpa.modelos.identidad import Asignacion, Rol, Sesion, Usuario
from fpa.modelos.mapeo import CuentaExcluidaMapeo, MapeoLineaCuenta, VersionMapeo
from fpa.modelos.organizacion import Hotel, Organizacion
from fpa.modelos.plan import LineaPlan, LineaPlanMensual, ValorCapturado, VersionPlan
from fpa.modelos.reporte import (
    ConvencionLinea,
    LineaReporte,
    ReglaSumaLinea,
    VersionEstructuraReporte,
)
from fpa.modelos.saldos import SaldoMensualCuenta

__all__ = [
    "Asignacion",
    "Base",
    "CargaArchivo",
    "ConvencionLinea",
    "CuentaExcluidaMapeo",
    "CuentaLocal",
    "EstadoCarga",
    "EventoAuditoria",
    "Hotel",
    "LineaPlan",
    "LineaPlanMensual",
    "LineaReporte",
    "MapeoLineaCuenta",
    "Movimiento",
    "Organizacion",
    "ReglaSumaLinea",
    "Rol",
    "SaldoMensualCuenta",
    "Sesion",
    "Usuario",
    "ValorCapturado",
    "VersionEstructuraReporte",
    "VersionMapeo",
    "VersionPlan",
]
