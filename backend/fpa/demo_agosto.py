"""Carga el agosto 2026 real en la base de DESARROLLO para revisar el reporte con Contraloría.

Uso (desde backend/, con la base ya migrada: `iniciar_servidores.bat` lo hace):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.demo_agosto --datos "C:\\ruta\\a\\la\\carpeta\\de\\datos"

La carpeta debe traer el Excel del Variance de **Mazatlán** (`02. MZT August 2026 Variance
(Envio).xlsx`) y, opcionalmente, `Catalogo de cuentas.xls` (da
nombre a las cuentas del desglose). Con `--archivo` se usa otro (p. ej. el de Vallarta, que se
detecta solo). Hace lo mismo que un analista y un contralor por la interfaz: carga los movimientos
de julio y agosto, importa la estructura, las reglas de suma y el mapeo, **excluye a propósito y
lista** las cuentas con movimiento que el Excel no toma en ninguna línea, aprueba el mapeo e
importa el Budget (mes a mes en Mazatlán). Es seguro repetirlo: si el mismo archivo ya está
cargado, no cambia nada.

**Solo desarrollo.** Se niega a correr si `FPA_ENTORNO` no es `desarrollo`. Las exclusiones son
PROVISIONALES hasta que Contraloría responda por esas cuentas (docs/HALLAZGOS_CONTRALORIA.md) y la
pantalla lo avisa. Con el servidor ya corriendo, la caché de reportes vence a los 5 minutos (o
reinícialo).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select

from fpa.calculo.ano_fiscal import etiqueta_ano_fiscal
from fpa.config import settings
from fpa.db import SessionLocal
from fpa.ingesta.budget_anual_mzt import alinear_con_lineas, leer_budget_anual
from fpa.ingesta.formato_variance import Formato
from fpa.ingesta.novohit_con020 import leer_con020
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.ingesta.variance_convenciones import leer_convenciones
from fpa.ingesta.variance_lectura import leer_variance
from fpa.ingesta.variance_mzt import leer_hojas_mzt, leer_valores_mensuales_mzt
from fpa.ingesta.variance_valores import leer_variance_valores
from fpa.modelos.identidad import Usuario
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.semilla import sembrar_torres
from fpa.servicios.budget import (
    importar_actuales_capturados,
    importar_budget,
    importar_budget_mensual,
)
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.catalogo_oficial import importar_catalogo
from fpa.servicios.convenciones_linea import importar_convenciones
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.omitir_cuentas import MOTIVO_NO_SE_OCUPAN
from fpa.servicios.reglas_suma import importar_reglas_suma
from fpa.servicios.validacion_mapeo import CuentaSinMapear, validar_mapeo
from fpa.servicios.versionado_mapeo import aprobar, excluir_cuenta

EXCEL = "02. MZT August 2026 Variance (Envio).xlsx"
VARIACION = (
    "02. MZT August 2026 Variance.xlsx"  # sus columnas G, L y Q dan el sentido de la Variación
)
CATALOGO = "Catalogo de cuentas.xls"
BUDGET_ANUAL = "Budget MZT 26-27.xlsx"  # el Budget de los 12 meses del año fiscal y su total
PERIODO_CORTE = "2026-08"
PERIODOS = ["2026-07", "2026-08"]
MOTIVO = MOTIVO_NO_SE_OCUPAN  # Contraloría: estas cuentas todavía no se ocupan


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_demo(carpeta: Path, imprimir=print, archivo_excel: str = EXCEL) -> None:  # type: ignore[no-untyped-def]
    if settings.entorno != "desarrollo":
        raise SystemExit(
            "Este script solo corre con FPA_ENTORNO=desarrollo: carga datos reales de Torres en "
            "la base y usa la identidad de desarrollo."
        )
    excel = carpeta / archivo_excel
    if not excel.exists():
        raise SystemExit(f"No encuentro {archivo_excel} en {carpeta}")
    sha = _sha256(excel)
    archivo = DatosArchivo(nombre=excel.name, sha256=sha, tamano_bytes=excel.stat().st_size)

    with SessionLocal() as db:
        hotel = sembrar_torres(db)
        db.commit()
        contralor = db.scalar(select(Usuario).where(Usuario.email == "contralor@torres.local"))
        analista = db.scalar(select(Usuario).where(Usuario.email == "analista@torres.local"))
        if contralor is None or analista is None:
            raise SystemExit("Faltan los usuarios de desarrollo: corre `python -m fpa.semilla`")
        base: dict[str, Any] = {"organizacion_id": hotel.organizacion_id, "hotel_id": hotel.id}
        imprimir(f"Hotel: {hotel.nombre} (id {hotel.id})")

        catalogo = carpeta / CATALOGO
        if catalogo.exists():
            r = importar_catalogo(db, hotel_id=hotel.id, catalogo=leer_con020(catalogo))
            db.commit()
            imprimir(f"Catálogo oficial: {r.total_cuentas} cuentas ({r.creadas} nuevas)")

        imprimir("Leyendo los movimientos de julio y agosto…")
        carga = cargar_archivo(
            db,
            usuario_id=analista.id,
            resultado=leer_variance_base_datos(excel),
            archivo=archivo,
            confirmar_reemplazo=True,
            **base,
        )
        db.commit()
        if carga.resolucion is Resolucion.RECHAZADA:
            raise SystemExit(f"Movimientos rechazados: {carga.motivos}")
        imprimir(f"Movimientos: {carga.resolucion.value}")

        imprimir("Leyendo la estructura, las reglas y el mapeo de la hoja Ago…")
        lectura = leer_variance(excel)
        estructura = lectura.estructura
        imprimir(f"Formato detectado: {lectura.formato.value}")
        res_est = importar_estructura_reporte(
            db,
            usuario_id=analista.id,
            resultado=estructura,
            archivo=archivo,
            periodo_referencia=PERIODO_CORTE,
            confirmar_reemplazo=True,
            **base,
        )
        db.commit()
        version = res_est.version
        if version is None:
            raise SystemExit(f"Estructura rechazada: {res_est.motivos}")
        importar_reglas_suma(
            db,
            usuario_id=analista.id,
            version=version,
            leidas=lectura.reglas,
            **base,
        )

        repo = RepositorioMapeo(db, hotel.id)
        aprobada = repo.aprobada()
        if (
            aprobada is not None
            and aprobada.origen == excel.name
            and res_est.resolucion is (Resolucion.DUPLICADA)
        ):
            db.commit()
            imprimir(f"El mapeo v{aprobada.numero} ya estaba aprobado: no se repite.")
        else:
            mapeo = importar_mapeo(
                db,
                usuario_id=analista.id,
                version_estructura=version,
                leido=lectura.mapeo,
                archivo=archivo,
                confirmar_reemplazo=True,
                **base,
            ).version
            if mapeo is None:
                raise SystemExit("No se pudo crear el borrador del mapeo")
            sin_linea: dict[str, CuentaSinMapear] = {}
            for periodo in PERIODOS:
                reporte = validar_mapeo(
                    db, hotel_id=hotel.id, version_mapeo_id=mapeo.id, periodo=periodo
                )
                for c in reporte.sin_mapear:
                    sin_linea.setdefault(c.cuenta_codigo, c)
            for c in sin_linea.values():
                excluir_cuenta(
                    db,
                    usuario_id=analista.id,
                    version_id=mapeo.id,
                    cuenta_codigo=c.cuenta_codigo,
                    motivo=MOTIVO,
                    **base,
                )
            aprobar(
                db,
                usuario_id=contralor.id,
                version_id=mapeo.id,
                periodos=PERIODOS,
                notas="Demostración de agosto 2026 (cuentas que todavía no se ocupan)",
                **base,
            )
            db.commit()
            imprimir(f"Mapeo v{mapeo.numero} aprobado; {len(sin_linea)} cuentas excluidas:")
            for c in sorted(sin_linea.values(), key=lambda x: -abs(x.neto)):
                imprimir(f"  {c.cuenta_codigo}  {c.neto:>16,.2f}  {c.descripcion or ''}")

        presupuesto = next((p for p in (carpeta / BUDGET_ANUAL,) if p.exists()), None)
        if lectura.formato is Formato.MZT and presupuesto is not None:
            # El Budget de todo el año fiscal (12 meses + anual) manda sobre el pegado en el Excel
            alineado = alinear_con_lineas(
                leer_budget_anual(presupuesto),
                [
                    (x.fila_origen, x.descripcion)
                    for x in RepositorioReporte(db, hotel.id).lineas(version.id)
                    if x.tipo != "seccion"
                ],
                {
                    x.fila_origen
                    for x in RepositorioReporte(db, hotel.id).lineas(version.id)
                    if x.tipo == "detalle"
                },
            )
            res_budget = importar_budget_mensual(
                db,
                usuario_id=analista.id,
                version_estructura=version,
                por_periodo=alineado.por_periodo,
                anual=alineado.anual,
                archivo=DatosArchivo(
                    nombre=presupuesto.name,
                    sha256=_sha256(presupuesto),
                    tamano_bytes=presupuesto.stat().st_size,
                ),
                ano_fiscal=alineado.ano_fiscal,
                confirmar_reemplazo=True,
                **base,
            )
        elif lectura.formato is Formato.MZT:
            res_budget = importar_budget_mensual(
                db,
                usuario_id=analista.id,
                version_estructura=version,
                por_periodo=leer_valores_mensuales_mzt(leer_hojas_mzt(excel)).por_periodo,
                archivo=archivo,
                ano_fiscal=etiqueta_ano_fiscal(PERIODO_CORTE),
                filas_con_cuentas={v.fila_origen for v in lectura.mapeo.vinculos},
                confirmar_reemplazo=True,
                **base,
            )
        else:
            res_budget = importar_budget(
                db,
                usuario_id=analista.id,
                version_estructura=version,
                valores=leer_variance_valores(excel),
                archivo=archivo,
                periodo_corte=PERIODO_CORTE,
                ano_fiscal=etiqueta_ano_fiscal(PERIODO_CORTE),
                confirmar_reemplazo=True,
                **base,
            )
        db.commit()
        imprimir(f"Budget: {res_budget.resolucion.value}")

        if lectura.formato is Formato.MZT and presupuesto is not None:
            # El Budget anual no trae Actuals: el tipo de cambio y las líneas sin cuentas de julio y
            # agosto salen del Excel de Contraloría (septiembre en adelante se captura a mano)
            capturados = importar_actuales_capturados(
                db,
                usuario_id=analista.id,
                version_estructura=version,
                por_periodo=leer_valores_mensuales_mzt(leer_hojas_mzt(excel)).por_periodo,
                filas_con_cuentas={v.fila_origen for v in lectura.mapeo.vinculos},
                archivo=excel.name,
                **base,
            )
            db.commit()
            imprimir(f"Actual capturado del Excel de Contraloría: {capturados} valores")

        if lectura.formato is Formato.MZT:
            variacion = next((p for p in (carpeta / VARIACION,) if p.exists()), None)
            if variacion is not None:
                celdas, _sin = importar_convenciones(
                    db,
                    usuario_id=analista.id,
                    version=version,
                    leidas=leer_convenciones(variacion),
                    archivo=variacion.name,
                    **base,
                )
                db.commit()
                imprimir(f"Sentido de la Variación leído de {variacion.name}: {celdas} celdas")

    imprimir("")
    imprimir("Listo. Abre http://localhost:5180 (iniciar_servidores.bat) y entra como Analista o")
    imprimir("Contralor: pestaña Variance, mes 2026-08. Guía: docs/GUIA_PRUEBA_CONTRALORIA.md")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--datos",
        type=Path,
        required=True,
        help="Carpeta con el Excel del Variance de agosto (y, opcional, el catálogo CON020)",
    )
    parser.add_argument("--archivo", default=EXCEL, help="Nombre del Excel (por omisión, Mazatlán)")
    args = parser.parse_args()
    cargar_demo(args.datos, archivo_excel=args.archivo)


if __name__ == "__main__":
    main()
