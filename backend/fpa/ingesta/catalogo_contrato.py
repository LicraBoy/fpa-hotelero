"""Resultado de leer el catálogo contable oficial (reporte CON020 de Novohit)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CuentaCatalogo:
    codigo: str  # '1000001' (cuenta base) o '1000001.001' (subcuenta)
    descripcion: str
    tipo: str  # 'Deudor' | 'Acreedor'
    auxiliar: bool
    activa: bool
    grupo_ef: str | None  # GRUPO E.F (grupo del estado financiero)
    depto_ef: str | None  # DEPTO EdoFro (departamento del estado de resultados)
    depto_ti: str | None  # DPTO. TI
    cuenta_terceros: str | None
    cuenta_sat: str | None  # código agrupador del SAT con su nombre
    fila: int


@dataclass
class TituloCatalogo:
    """Nivel de la jerarquía con nombre: 1 (clase), 2, o 4 dígitos (grupo)."""

    codigo: str
    descripcion: str
    fila: int


@dataclass
class ResultadoCatalogo:
    empresa: str | None = None
    fecha_emision: str | None = None
    cuentas: list[CuentaCatalogo] = field(default_factory=list)
    titulos: list[TituloCatalogo] = field(default_factory=list)
    filas_ignoradas: int = 0
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores and bool(self.cuentas)
