"""Contrato común de lectura.

Cada lector de archivos (CON130 de Novohit, hoja "Base de Datos" del Variance, ...) entrega un
`ResultadoLectura`. Así la persistencia, la calidad de datos y el catálogo no dependen del
formato del archivo de origen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

CENTAVO = Decimal("0.01")
CERO = Decimal("0")


class Fuente(StrEnum):
    CON130 = "con130"
    VARIANCE_BASE_DATOS = "variance_base_datos"


@dataclass
class Movimiento:
    cuenta_codigo: str
    cuenta_descripcion: str
    asiento: str
    fecha: date
    concepto: str | None
    debito: Decimal
    credito: Decimal
    fila: int
    tp_asiento: str | None = None
    operacion: str | None = None
    tp_doc: str | None = None
    numero: str | None = None
    saldo: Decimal | None = None
    cantidad: Decimal | None = None
    costo: Decimal | None = None

    @property
    def periodo(self) -> str:
        return f"{self.fecha.year:04d}-{self.fecha.month:02d}"


@dataclass
class Cuenta:
    codigo: str
    descripcion: str
    fila: int
    saldo_anterior: Decimal | None = None
    suma_debito: Decimal = CERO
    suma_credito: Decimal = CERO
    total_debito_reporte: Decimal | None = None
    total_credito_reporte: Decimal | None = None
    # True = el Total del reporte coincide; False = no coincide; None = no trae Total
    total_verificado: bool | None = None


@dataclass
class Titulo:
    """Título de la jerarquía de cuentas (ej. `1000001 BANCOS MONEDA NACIONAL`)."""

    codigo: str
    descripcion: str | None
    fila: int


@dataclass
class ResultadoLectura:
    fuente: Fuente | None = None
    # Las fuentes que son un libro completo deben cuadrar Débito = Crédito; las que son un
    # subconjunto de cuentas (p. ej. solo resultados) no.
    controla_balance: bool = True
    # Texto del periodo que declara el propio reporte, si lo trae (ej. CON130)
    periodo_texto: str | None = None
    movimientos: list[Movimiento] = field(default_factory=list)
    cuentas: dict[str, Cuenta] = field(default_factory=dict)
    titulos: list[Titulo] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def total_debito(self) -> Decimal:
        return sum((m.debito for m in self.movimientos), CERO)

    @property
    def total_credito(self) -> Decimal:
        return sum((m.credito for m in self.movimientos), CERO)

    @property
    def cuadra_debito_credito(self) -> bool:
        return abs(self.total_debito - self.total_credito) < CENTAVO

    @property
    def periodos(self) -> list[str]:
        """Periodos (`AAAA-MM`) presentes en los movimientos, ordenados."""
        return sorted({m.periodo for m in self.movimientos})

    @property
    def fecha_min(self) -> date | None:
        return min((m.fecha for m in self.movimientos), default=None)

    @property
    def fecha_max(self) -> date | None:
        return max((m.fecha for m in self.movimientos), default=None)

    @property
    def es_valido(self) -> bool:
        return not self.errores and (self.cuadra_debito_credito or not self.controla_balance)
