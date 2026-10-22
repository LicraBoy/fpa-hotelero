"""Registro (logging) estructurado en JSON, con `request_id` de correlación (Fase 6.5).

Sustituye los `logging.getLogger(__name__)` sueltos: cada línea de log de la aplicación sale en
JSON con el mismo `request_id` que la petición HTTP que la originó, para poder seguirle el rastro
a una petición a través de varias líneas de log.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def id_de_peticion_actual() -> str | None:
    return _request_id.get()


def fijar_id_de_peticion(valor: str | None) -> None:
    _request_id.set(valor)


class FormateadorJSON(logging.Formatter):
    """Una línea de log = un objeto JSON (`timestamp`, `nivel`, `logger`, `mensaje`,
    `request_id` si hay una petición en curso, y `excepcion` si la hay)."""

    def format(self, registro: logging.LogRecord) -> str:
        cuerpo: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(registro.created, tz=UTC).isoformat(),
            "nivel": registro.levelname,
            "logger": registro.name,
            "mensaje": registro.getMessage(),
        }
        id_peticion = id_de_peticion_actual()
        if id_peticion is not None:
            cuerpo["request_id"] = id_peticion
        if registro.exc_info:
            cuerpo["excepcion"] = self.formatException(registro.exc_info)
        return json.dumps(cuerpo, ensure_ascii=False)


def configurar_registro(nivel: int = logging.INFO) -> None:
    """Llamar una sola vez al arrancar la aplicación (ver `fpa/main.py`)."""
    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    raiz.handlers.clear()
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJSON())
    raiz.addHandler(manejador)
