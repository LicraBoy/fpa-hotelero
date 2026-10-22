"""Alerta mínima (Fase 6.5): sin asumir Grafana/Prometheus/Slack ya configurados.

Sin `FPA_ALERTA_WEBHOOK`, una alerta es una línea de log en `CRITICAL` (siempre visible en
`logs/`, aunque nadie la vea en el momento). Con la variable puesta, además manda un POST con
`{"texto": mensaje}` — funciona con un webhook de Slack/Teams o cualquier endpoint propio que
reciba JSON. Un fallo al mandar la alerta nunca debe tumbar lo que la disparó: se registra y se
sigue.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def alertar(mensaje: str) -> None:
    log.critical("ALERTA: %s", mensaje)
    webhook = os.environ.get("FPA_ALERTA_WEBHOOK")
    if not webhook:
        return
    try:
        import httpx

        httpx.post(webhook, json={"texto": mensaje}, timeout=5.0)
    except Exception:
        log.exception("No se pudo enviar la alerta al webhook (se queda solo en el log)")
