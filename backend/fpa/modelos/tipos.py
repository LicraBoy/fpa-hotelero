"""Tipos de columna propios.

`Dinero`: los montos NUNCA son float.
- PostgreSQL (y otros): `NUMERIC(18,2)`.
- SQLite: no tiene decimales exactos (SQLAlchemy los convertiría a float), así que se guardan
  como texto canónico ("1234.50"). Por eso las sumas se hacen en Python con `Decimal`,
  no con SUM() de SQL. Ver docs/adr/0002-dinero-en-sqlite.md.

`Medida`: cantidades y costos unitarios (hasta 6 decimales exactos), con la misma estrategia.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Dialect, Numeric, String
from sqlalchemy.types import TypeDecorator, TypeEngine

CENTAVO = Decimal("0.01")
MICRO = Decimal("0.000001")


class _DecimalExacto(TypeDecorator[Decimal]):
    """Base: decimal exacto; texto canónico en SQLite, NUMERIC en los demás motores."""

    impl = Numeric
    cache_ok = True
    _precision = 18
    _escala = 2
    _paso = CENTAVO

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(40))
        return dialect.type_descriptor(Numeric(self._precision, self._escala, asdecimal=True))

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("Los montos deben ser Decimal, nunca float")
        if not isinstance(value, Decimal):
            raise TypeError(f"Valor inválido: {value!r}")
        exacto = value.quantize(self._paso)
        if exacto != value:
            raise ValueError(f"El valor {value} tiene más de {self._escala} decimales")
        return format(exacto, "f") if dialect.name == "sqlite" else exacto

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value)).quantize(self._paso)


class Dinero(_DecimalExacto):
    """Montos en moneda: dos decimales exactos."""

    cache_ok = True
    _precision = 18
    _escala = 2
    _paso = CENTAVO


class Medida(_DecimalExacto):
    """Cantidades y costos unitarios: hasta seis decimales exactos."""

    cache_ok = True
    _precision = 20
    _escala = 6
    _paso = MICRO
