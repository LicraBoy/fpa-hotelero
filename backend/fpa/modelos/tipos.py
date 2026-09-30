"""Tipos de columna propios.

`Dinero`: los montos NUNCA son float.
- PostgreSQL (y otros): `NUMERIC(18,2)`.
- SQLite: no tiene decimales exactos (SQLAlchemy los convertiría a float), así que se guardan
  como texto canónico ("1234.50"). Por eso las sumas se hacen en Python con `Decimal`,
  no con SUM() de SQL. Ver docs/adr/0002-dinero-en-sqlite.md.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Dialect, Numeric, String
from sqlalchemy.types import TypeDecorator, TypeEngine

CENTAVO = Decimal("0.01")


class Dinero(TypeDecorator[Decimal]):
    impl = Numeric
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(40))
        return dialect.type_descriptor(Numeric(18, 2, asdecimal=True))

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("Los montos deben ser Decimal, nunca float")
        if not isinstance(value, Decimal):
            raise TypeError(f"Monto inválido: {value!r}")
        exacto = value.quantize(CENTAVO)
        if exacto != value:
            raise ValueError(f"El monto {value} tiene más de dos decimales")
        return format(exacto, "f") if dialect.name == "sqlite" else exacto

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value)).quantize(CENTAVO)
