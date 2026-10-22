"""Métricas mínimas para Prometheus (Fase 6.5). Sin asumir que ya hay Grafana/Prometheus
instalado: el endpoint `/metrics` sirve el formato de texto estándar, lo use quien lo use."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

PETICIONES_TOTAL = Counter(
    "fpa_peticiones_total",
    "Peticiones HTTP atendidas",
    ["method", "ruta", "estado"],
)

PETICIONES_DURACION_S = Histogram(
    "fpa_peticiones_duracion_segundos",
    "Duración de las peticiones HTTP",
    ["method", "ruta"],
)

RESPALDO_FALLOS_TOTAL = Counter(
    "fpa_respaldo_fallos_total",
    "Intentos de respaldo que fallaron (ADR 0010)",
)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "PETICIONES_DURACION_S",
    "PETICIONES_TOTAL",
    "RESPALDO_FALLOS_TOTAL",
    "exponer_metricas",
]


def exponer_metricas() -> tuple[bytes, str]:
    """Usado por el endpoint `/metrics` (`fpa/api/health.py`): cuerpo + content-type."""
    return generate_latest(), CONTENT_TYPE_LATEST
