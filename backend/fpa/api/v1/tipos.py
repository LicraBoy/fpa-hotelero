"""Tipos comunes de los esquemas de la API."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Path, Query
from pydantic import AfterValidator


def _con_zona_utc(valor: datetime) -> datetime:
    """SQLite devuelve fechas sin zona; el sistema guarda todo en UTC, así que se declara."""
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor.astimezone(UTC)


FechaHoraUtc = Annotated[datetime, AfterValidator(_con_zona_utc)]

# Los ids son enteros de 32 bits positivos: un valor fuera de rango no puede existir y no debe
# llegar a la base de datos (SQLite lo rechaza con un error, que sería un 500).
ID_MAX = 2_147_483_647
IdRuta = Annotated[int, Path(ge=1, le=ID_MAX)]
IdConsulta = Annotated[int, Query(ge=1, le=ID_MAX)]
