"""La caché de reportes de esta aplicación (una por proceso)."""

from typing import Any

from fpa.config import settings
from fpa.servicios.cache_reportes import CacheReportes

# Se guarda el Variance completo (sin filtros): (modelo de respuesta, su JSON ya serializado).
cache_variance: CacheReportes[tuple[Any, bytes]] = CacheReportes(
    ttl_segundos=settings.cache_reportes_ttl_s, max_entradas=settings.cache_reportes_max
)
