"""Prueba de carga/rendimiento (Fase 6.3, §4.5 del plan). Sin Locust/k6 (dependencia nueva): un
script async con `httpx` (ya es dependencia de pruebas) basta para medir contra la API real.

Objetivos (§4.5, `[PROPUESTA]`, se miden aquí):
  - Variance mensual (~400 líneas): p95 < 500 ms con caché, < 2 s sin caché.
  - Carga de un CON130 de 10 mil filas: < 10 s.
  - 50 usuarios concurrentes sin degradar (se mide como: la mediana con 50 a la vez no empeora
    más de ~2x frente a una sola petición).

Uso (backend corriendo en :8100, con el mapeo/budget de Mazatlán ya aprobados):
    .venv\\Scripts\\python scripts/prueba_de_carga.py
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = "http://127.0.0.1:8100"
CABECERAS = {"X-Usuario-Dev": "contralor@torres.local"}
HOTEL_ID = 1
PERIODO = "2026-08"
CONCURRENCIA = 50


async def _una_peticion(cliente: httpx.AsyncClient) -> float:
    inicio = time.perf_counter()
    r = await cliente.get(
        f"/api/v1/hoteles/{HOTEL_ID}/variance",
        params={"periodo": PERIODO},
        headers=CABECERAS,
    )
    r.raise_for_status()
    return time.perf_counter() - inicio


def _reportar(nombre: str, duraciones: list[float], objetivo_s: float) -> bool:
    duraciones.sort()
    p50 = statistics.median(duraciones)
    p95 = duraciones[int(len(duraciones) * 0.95) - 1] if len(duraciones) > 1 else duraciones[0]
    cumple = p95 < objetivo_s
    estado = "OK" if cumple else "NO CUMPLE"
    print(
        f"{nombre}: p50={p50 * 1000:.0f} ms  p95={p95 * 1000:.0f} ms  "
        f"(objetivo p95<{objetivo_s * 1000:.0f} ms) [{estado}]"
    )
    return cumple


async def medir_variance_sin_cache(cliente: httpx.AsyncClient) -> bool:
    # Fuerza una caché fría: cambia un filtro irrelevante (q) en cada llamada para no pegarle
    # siempre a la misma clave de caché (ver fpa/servicios/cache_reportes.py).
    duraciones = []
    for i in range(10):
        inicio = time.perf_counter()
        r = await cliente.get(
            f"/api/v1/hoteles/{HOTEL_ID}/variance",
            params={"periodo": PERIODO, "q": f"__carga_{i}__"},
            headers=CABECERAS,
        )
        r.raise_for_status()
        duraciones.append(time.perf_counter() - inicio)
    return _reportar("Variance SIN caché", duraciones, objetivo_s=2.0)


async def medir_variance_con_cache(cliente: httpx.AsyncClient) -> bool:
    await cliente.get(
        f"/api/v1/hoteles/{HOTEL_ID}/variance", params={"periodo": PERIODO}, headers=CABECERAS
    )  # calienta la caché
    duraciones = [await _una_peticion(cliente) for _ in range(20)]
    return _reportar("Variance CON caché", duraciones, objetivo_s=0.5)


async def medir_concurrencia(cliente: httpx.AsyncClient) -> bool:
    linea_base = statistics.median([await _una_peticion(cliente) for _ in range(5)])
    duraciones = await asyncio.gather(*[_una_peticion(cliente) for _ in range(CONCURRENCIA)])
    mediana_concurrente = statistics.median(duraciones)
    degradacion = mediana_concurrente / linea_base if linea_base > 0 else float("inf")
    cumple = degradacion < 2.0
    estado = "OK" if cumple else "NO CUMPLE"
    print(
        f"{CONCURRENCIA} usuarios concurrentes: línea base={linea_base * 1000:.0f} ms, "
        f"mediana concurrente={mediana_concurrente * 1000:.0f} ms, "
        f"degradación={degradacion:.1f}x (objetivo <2x) [{estado}]"
    )
    return cumple


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as cliente:
        try:
            await cliente.get("/api/health")
        except httpx.ConnectError:
            print(f"ERROR: no responde {BASE_URL} (¿está corriendo el backend?)", file=sys.stderr)
            return 1

        resultados = [
            await medir_variance_con_cache(cliente),
            await medir_variance_sin_cache(cliente),
            await medir_concurrencia(cliente),
        ]
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
