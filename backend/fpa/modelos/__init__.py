"""Importa todos los modelos para que Alembic y `Base.metadata` los conozcan."""

from fpa.modelos.auditoria import EventoAuditoria
from fpa.modelos.base import Base
from fpa.modelos.cargas import CargaArchivo, EstadoCarga, Movimiento
from fpa.modelos.catalogo import CuentaLocal
from fpa.modelos.cierre import CierrePeriodo, CierreTransicion
from fpa.modelos.comentarios import AdjuntoComentario, ComentarioLinea, ComentarioRevision
from fpa.modelos.identidad import Asignacion, AsignacionDepartamento, Rol, Sesion, Usuario
from fpa.modelos.mapeo import CuentaExcluidaMapeo, MapeoLineaCuenta, VersionMapeo
from fpa.modelos.organizacion import Hotel, Organizacion
from fpa.modelos.plan import LineaPlan, LineaPlanMensual, ValorCapturado, VersionPlan
from fpa.modelos.presupuesto import (
    AnoFiscal,
    CicloPresupuesto,
    CicloTransicion,
    ConsumoLineaMes,
    DetalleLineaPresupuesto,
    HojaSeccionMes,
    InflacionLineaMes,
    LineaPlanDetalle,
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
    PartidaLinea,
    PartidaMes,
    PerfilDistribucion,
    PeriodoFiscal,
    ReferenciaLineaMes,
)
from fpa.modelos.reporte import (
    ConvencionLinea,
    LineaReporte,
    ReglaSumaLinea,
    VersionEstructuraReporte,
)
from fpa.modelos.saldos import SaldoMensualCuenta

__all__ = [
    "AdjuntoComentario",
    "AnoFiscal",
    "Asignacion",
    "AsignacionDepartamento",
    "Base",
    "CargaArchivo",
    "CicloPresupuesto",
    "CicloTransicion",
    "CierrePeriodo",
    "CierreTransicion",
    "ComentarioLinea",
    "ComentarioRevision",
    "ConsumoLineaMes",
    "ConvencionLinea",
    "CuentaExcluidaMapeo",
    "CuentaLocal",
    "DetalleLineaPresupuesto",
    "EstadoCarga",
    "EventoAuditoria",
    "HojaSeccionMes",
    "Hotel",
    "InflacionLineaMes",
    "LineaPlan",
    "LineaPlanDetalle",
    "LineaPlanMensual",
    "LineaPresupuestoCaptura",
    "LineaPresupuestoMensual",
    "LineaReporte",
    "MapeoLineaCuenta",
    "Movimiento",
    "Organizacion",
    "PartidaLinea",
    "PartidaMes",
    "PerfilDistribucion",
    "PeriodoFiscal",
    "ReferenciaLineaMes",
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
