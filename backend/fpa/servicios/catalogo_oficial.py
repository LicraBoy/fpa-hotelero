"""Importación del catálogo contable oficial (reporte CON020 de Novohit).

El catálogo oficial manda en nombre, tipo (Deudor/Acreedor) y clasificaciones. Las cuentas que el
hotel ya conocía solo por sus movimientos se conservan y se marcan como fuera del catálogo oficial.
Es idempotente: importar el mismo contenido otra vez no cambia nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from fpa.ingesta.catalogo_contrato import ResultadoCatalogo
from fpa.modelos.catalogo import CuentaLocal
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.servicios.catalogo import calcular_niveles, calcular_padres


@dataclass
class ResumenImportacion:
    total_cuentas: int = 0
    total_titulos: int = 0
    creadas: int = 0
    actualizadas: int = 0
    sin_cambio: int = 0
    titulos_con_nombre_nuevo: int = 0
    fuera_del_catalogo: list[str] = field(default_factory=list)
    inactivas_con_movimientos: list[str] = field(default_factory=list)

    @property
    def hubo_cambios(self) -> bool:
        return bool(self.creadas or self.actualizadas)


_CAMPOS = (
    "descripcion",
    "nivel",
    "padre_codigo",
    "es_titulo",
    "con_movimientos",
    "sin_jerarquia",
    "tipo",
    "grupo_ef",
    "depto_ef",
    "depto_ti",
    "cuenta_terceros",
    "cuenta_sat",
    "auxiliar",
    "activa",
    "en_catalogo_oficial",
)


def importar_catalogo(
    db: Session, *, hotel_id: int, catalogo: ResultadoCatalogo
) -> ResumenImportacion:
    existentes = RepositorioCatalogo(db, hotel_id).por_codigo()
    oficiales = {c.codigo: c for c in catalogo.cuentas}
    titulos = {t.codigo: t.descripcion for t in catalogo.titulos}
    con_subcuentas = {c.codigo.split(".")[0] for c in catalogo.cuentas if "." in c.codigo}

    # Una cuenta base con subcuentas (1000001) es un grupo, igual que en el CON130.
    codigos_titulo = (
        set(titulos) | con_subcuentas | {c.codigo for c in existentes.values() if c.es_titulo}
    )
    todos = set(existentes) | set(oficiales) | set(titulos)
    padres = calcular_padres(codigos_titulo, todos, conocidos=todos)
    niveles = calcular_niveles(padres)

    resumen = ResumenImportacion(total_cuentas=len(oficiales), total_titulos=len(titulos))
    for codigo in sorted(todos):
        fila = existentes.get(codigo)
        oficial = oficiales.get(codigo)
        con_movimientos = fila.con_movimientos if fila is not None else False
        padre = padres[codigo]
        nombre_oficial = oficial.descripcion if oficial else titulos.get(codigo)
        valores: dict[str, Any] = {
            "descripcion": nombre_oficial or (fila.descripcion if fila else None),
            "nivel": niveles.get(codigo),
            "padre_codigo": padre,
            "es_titulo": codigo in codigos_titulo,
            "con_movimientos": con_movimientos,
            "sin_jerarquia": con_movimientos and padre is None,
            "en_catalogo_oficial": oficial is not None or codigo in titulos,
        }
        if oficial is not None:
            valores.update(
                tipo=oficial.tipo,
                grupo_ef=oficial.grupo_ef,
                depto_ef=oficial.depto_ef,
                depto_ti=oficial.depto_ti,
                cuenta_terceros=oficial.cuenta_terceros,
                cuenta_sat=oficial.cuenta_sat,
                auxiliar=oficial.auxiliar,
                activa=oficial.activa,
            )
        elif fila is not None:
            valores.update({k: getattr(fila, k) for k in _CAMPOS[6:14]})
        else:
            valores.update(
                tipo=None,
                grupo_ef=None,
                depto_ef=None,
                depto_ti=None,
                cuenta_terceros=None,
                cuenta_sat=None,
                auxiliar=False,
                activa=True,
            )

        if codigo in titulos and (fila is None or fila.descripcion != titulos[codigo]):
            resumen.titulos_con_nombre_nuevo += 1
        if fila is None:
            db.add(
                CuentaLocal(
                    hotel_id=hotel_id,
                    codigo=codigo,
                    clase=codigo[0],
                    origen="catalogo_oficial",
                    **valores,
                )
            )
            resumen.creadas += 1
        elif any(getattr(fila, k) != valores[k] for k in _CAMPOS):
            for k in _CAMPOS:
                setattr(fila, k, valores[k])
            resumen.actualizadas += 1
        else:
            resumen.sin_cambio += 1

        if fila is not None and fila.con_movimientos:
            if oficial is None and codigo not in titulos:
                resumen.fuera_del_catalogo.append(codigo)
            elif oficial is not None and not oficial.activa:
                resumen.inactivas_con_movimientos.append(codigo)
    db.flush()
    return resumen
