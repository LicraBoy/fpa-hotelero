"""Catálogo local de cuentas: jerarquía por prefijo de código y acumulación entre cargas.

El CON130 trae títulos de jerarquía (`1` > `10` > `1000` > `1000001` > `1000001.001`). El padre de
una cuenta es el candidato **más largo** entre:
- los títulos que son prefijo propio de su código, y
- su código base, si la cuenta es una subcuenta con punto (`1000001.001` -> `1000001`) y ese
  código base se conoce.

Verificado con septiembre 2026: las 366 cuentas con movimientos tienen al menos un título ancestro.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.contrato import ResultadoLectura
from fpa.modelos.catalogo import CuentaLocal
from fpa.repositorios.catalogo import RepositorioCatalogo


class CatalogoInconsistente(ValueError):
    """La jerarquía de cuentas tiene un ciclo."""


def calcular_padres(
    codigos_titulo: Collection[str],
    codigos: Iterable[str],
    conocidos: Collection[str] | None = None,
) -> dict[str, str | None]:
    """Padre de cada código (o None si no se conoce). Ver la descripción del módulo."""
    titulos = sorted(set(codigos_titulo), key=len, reverse=True)
    todos = set(conocidos) if conocidos is not None else set()
    padres: dict[str, str | None] = {}
    for codigo in codigos:
        candidatos = [t for t in titulos if t != codigo and codigo.startswith(t)]
        if "." in codigo:
            base = codigo.rsplit(".", 1)[0]
            if base in todos:
                candidatos.append(base)
        padres[codigo] = max(candidatos, key=len) if candidatos else None
    return padres


def calcular_niveles(padres: Mapping[str, str | None]) -> dict[str, int]:
    """Profundidad de cada código (0 = raíz). Solo para los que se rastrean hasta una raíz."""
    niveles: dict[str, int] = {}

    def nivel(codigo: str, visitados: frozenset[str]) -> int | None:
        if codigo in niveles:
            return niveles[codigo]
        if codigo in visitados:
            raise CatalogoInconsistente(f"Ciclo en la jerarquía de cuentas en {codigo}")
        padre = padres.get(codigo)
        if padre is None:
            niveles[codigo] = 0
            return 0
        if padre not in padres:
            return None  # el padre aún no se conoce
        n = nivel(padre, visitados | {codigo})
        if n is None:
            return None
        niveles[codigo] = n + 1
        return n + 1

    for codigo in padres:
        nivel(codigo, frozenset())
    return niveles


@dataclass
class ResumenCatalogo:
    creadas: int = 0
    actualizadas: int = 0


def actualizar_catalogo(
    db: Session,
    *,
    hotel_id: int,
    resultado: ResultadoLectura,
    movimientos: list[MovimientoLeido] | None = None,
) -> ResumenCatalogo:
    """Agrega al catálogo las cuentas con movimientos y los títulos de la lectura.

    Acumula entre cargas y recalcula la jerarquía de **todas** las cuentas conocidas, porque un
    CON130 nuevo puede dar el título que a una cuenta del Variance le faltaba.
    """
    movs = resultado.movimientos if movimientos is None else movimientos
    existentes = RepositorioCatalogo(db, hotel_id).por_codigo()

    con_mov: dict[str, str] = {}
    for m in movs:
        con_mov.setdefault(m.cuenta_codigo, m.cuenta_descripcion)
    for codigo in con_mov:
        cuenta = resultado.cuentas.get(codigo)
        if cuenta is not None and cuenta.descripcion:
            con_mov[codigo] = cuenta.descripcion
    titulos = {t.codigo: t.descripcion for t in resultado.titulos}

    codigos_titulo = {c.codigo for c in existentes.values() if c.es_titulo} | set(titulos)
    todos = set(existentes) | set(con_mov) | set(titulos)
    padres = calcular_padres(codigos_titulo, todos, conocidos=todos)
    niveles = calcular_niveles(padres)
    origen = resultado.fuente.value if resultado.fuente else "desconocido"

    resumen = ResumenCatalogo()
    for codigo in sorted(todos):
        fila = existentes.get(codigo)
        con_movimientos = codigo in con_mov or (fila is not None and fila.con_movimientos)
        es_titulo = codigo in codigos_titulo
        padre = padres[codigo]
        sin_jerarquia = con_movimientos and padre is None
        descripcion = con_mov.get(codigo) or titulos.get(codigo)
        if fila is None:
            db.add(
                CuentaLocal(
                    hotel_id=hotel_id,
                    codigo=codigo,
                    descripcion=descripcion,
                    clase=codigo[0],
                    nivel=niveles.get(codigo),
                    padre_codigo=padre,
                    con_movimientos=con_movimientos,
                    es_titulo=es_titulo,
                    sin_jerarquia=sin_jerarquia,
                    origen=origen,
                )
            )
            resumen.creadas += 1
            continue
        cambios = {
            "descripcion": (
                fila.descripcion
                if fila.en_catalogo_oficial and fila.descripcion
                else (descripcion or fila.descripcion)
            ),
            "nivel": niveles.get(codigo),
            "padre_codigo": padre,
            "con_movimientos": con_movimientos,
            "es_titulo": es_titulo,
            "sin_jerarquia": sin_jerarquia,
        }
        if any(getattr(fila, k) != v for k, v in cambios.items()):
            for k, v in cambios.items():
                setattr(fila, k, v)
            resumen.actualizadas += 1
    db.flush()
    return resumen


@dataclass
class NodoCatalogo:
    codigo: str
    descripcion: str | None
    clase: str
    nivel: int | None
    con_movimientos: bool
    es_titulo: bool
    sin_jerarquia: bool
    tipo: str | None = None
    grupo_ef: str | None = None
    depto_ef: str | None = None
    cuenta_sat: str | None = None
    activa: bool = True
    en_catalogo_oficial: bool = False
    hijos: list[NodoCatalogo] = field(default_factory=list)


def construir_arbol(cuentas: Iterable[CuentaLocal]) -> list[NodoCatalogo]:
    """Árbol anidado. Las raíces son los títulos de nivel 0 y las cuentas sin jerarquía conocida."""
    lista = sorted(cuentas, key=lambda x: x.codigo)
    nodos = {
        c.codigo: NodoCatalogo(
            codigo=c.codigo,
            descripcion=c.descripcion,
            clase=c.clase,
            nivel=c.nivel,
            con_movimientos=c.con_movimientos,
            es_titulo=c.es_titulo,
            sin_jerarquia=c.sin_jerarquia,
            tipo=c.tipo,
            grupo_ef=c.grupo_ef,
            depto_ef=c.depto_ef,
            cuenta_sat=c.cuenta_sat,
            activa=c.activa,
            en_catalogo_oficial=c.en_catalogo_oficial,
        )
        for c in lista
    }
    raices: list[NodoCatalogo] = []
    for c in lista:
        nodo = nodos[c.codigo]
        padre = nodos.get(c.padre_codigo) if c.padre_codigo else None
        (padre.hijos if padre is not None else raices).append(nodo)
    return raices
