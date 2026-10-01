"""Carga el agosto 2026 real en la base de DESARROLLO para revisar el reporte con Contraloría.

Uso (desde backend/, con la base ya migrada: `iniciar_servidores.bat` lo hace):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.demo_agosto --datos "C:\\ruta\\a\\la\\carpeta\\de\\datos"

La carpeta debe traer `02. VT August 2026 Variance (Envio) (1).xlsx` y, opcionalmente,
`Catalogo de cuentas.xls` (da nombre a las cuentas del desglose). Hace lo mismo que un analista y
un contralor por la interfaz: carga los movimientos de julio y agosto, importa la estructura, las
reglas de suma y el mapeo, **excluye a propósito** las cuentas `4002013` y `4003003`, aprueba el
mapeo e importa el Budget. Es seguro repetirlo: si el mismo archivo ya está cargado, no cambia nada.

**Solo desarrollo.** Se niega a correr si `FPA_ENTORNO` no es `desarrollo`. Las dos exclusiones
son PROVISIONALES hasta que Contraloría responda por esas cuentas (docs/FASES_FUTURAS.md) y la
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
from fpa.ingesta.novohit_con020 import leer_con020
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.ingesta.variance_estructura import leer_filas_hoja, leer_variance_estructura_filas
from fpa.ingesta.variance_mapeo import leer_variance_mapeo_filas
from fpa.ingesta.variance_reglas import leer_variance_reglas_filas
from fpa.ingesta.variance_valores import leer_variance_valores
from fpa.modelos.identidad import Usuario
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.semilla import sembrar_torres
from fpa.servicios.budget import importar_budget
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.catalogo_oficial import importar_catalogo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.reglas_suma import importar_reglas_suma
from fpa.servicios.versionado_mapeo import aprobar, excluir_cuenta

EXCEL = "02. VT August 2026 Variance (Envio) (1).xlsx"
CATALOGO = "Catalogo de cuentas.xls"
PERIODO_CORTE = "2026-08"
CUENTAS_EXCLUIDAS = ("4002013", "4003003")
MOTIVO = (
    "Provisional: tiene movimientos y la hoja Ago no la toma en ninguna línea; "
    "pendiente de la respuesta de Contraloría"
)


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_demo(carpeta: Path, imprimir=print) -> None:  # type: ignore[no-untyped-def]
    if settings.entorno != "desarrollo":
        raise SystemExit(
            "Este script solo corre con FPA_ENTORNO=desarrollo: carga datos reales de Torres en "
            "la base y usa la identidad de desarrollo."
        )
    excel = carpeta / EXCEL
    if not excel.exists():
        raise SystemExit(f"No encuentro {EXCEL} en {carpeta}")
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
        filas = leer_filas_hoja(excel)
        estructura = leer_variance_estructura_filas(filas)
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
            leidas=leer_variance_reglas_filas(filas, estructura),
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
                leido=leer_variance_mapeo_filas(filas, estructura),
                archivo=archivo,
                confirmar_reemplazo=True,
                **base,
            ).version
            if mapeo is None:
                raise SystemExit("No se pudo crear el borrador del mapeo")
            for cuenta in CUENTAS_EXCLUIDAS:
                excluir_cuenta(
                    db,
                    usuario_id=analista.id,
                    version_id=mapeo.id,
                    cuenta_codigo=cuenta,
                    motivo=MOTIVO,
                    **base,
                )
            aprobar(
                db,
                usuario_id=contralor.id,
                version_id=mapeo.id,
                periodos=["2026-07", "2026-08"],
                notas="Demostración de agosto 2026 (exclusiones provisionales)",
                **base,
            )
            db.commit()
            imprimir(f"Mapeo v{mapeo.numero} aprobado; excluidas: {', '.join(CUENTAS_EXCLUIDAS)}")

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
    args = parser.parse_args()
    cargar_demo(args.datos)


if __name__ == "__main__":
    main()
