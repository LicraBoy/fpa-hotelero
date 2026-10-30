"""Vincula a las secciones de gastos de Commercial Services las cuentas que Contraloría les asigna y
faltaban
(solo DESARROLLO).

Uso (desde backend/, con la base ya migrada):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.mapeo_comerciales

Mismo trámite que `mapeo_accounting`: el mapeo de Contraloría (hoja `PESO COMPARATIVO MZT` de «Mapeo
de Cuentas
Mazatlan (1).xlsx») comparado con el aprobado. En cada negocio solo faltaban Seniority Premium y
Education
Bonus (el Excel escribe `….01` para la prima de antigüedad: es `….010` en el catálogo y llama
«Severance Pay» a
Education Bonus). Crea una versión del mapeo por sección y es seguro repetirlo. Se usa `Sección#2`
porque cada
negocio tiene dos secciones con el mismo nombre (ventas y gastos); las cuentas van a la segunda.
"""

from __future__ import annotations

from sqlalchemy import select

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.vincular_cuentas import VinculoPedido, vincular_cuentas

# (sección de gastos, prefijo de las cuentas de nómina del departamento)
NEGOCIOS: tuple[tuple[str, str], ...] = (
    ("Travel Agency#2", "6015001"),
    ("Store#2", "6016001"),
    ("Cafeteria#2", "6018001"),
    ("Bar#2", "6005001"),
    ("Restaurant#2", "6014001"),
)


def pedidos_de(prefijo: str) -> tuple[VinculoPedido, ...]:
    return (
        VinculoPedido("Seniority Premium", f"{prefijo}.010"),
        VinculoPedido("Education Bonus", f"{prefijo}.011"),
    )


def main() -> None:
    if settings.entorno != "desarrollo":
        raise SystemExit("Este script solo corre con FPA_ENTORNO=desarrollo.")
    with SessionLocal() as db:
        hotel = sembrar_torres(db)
        db.commit()
        analista = db.scalar(select(Usuario).where(Usuario.email == "analista@torres.local"))
        contralor = db.scalar(select(Usuario).where(Usuario.email == "contralor@torres.local"))
        if analista is None or contralor is None:
            raise SystemExit("Faltan los usuarios de desarrollo: corre `python -m fpa.semilla`")
        for seccion, prefijo in NEGOCIOS:
            r = vincular_cuentas(
                db,
                organizacion_id=hotel.organizacion_id,
                hotel_id=hotel.id,
                editor_id=analista.id,
                aprobador_id=contralor.id,
                seccion=seccion,
                pedidos=pedidos_de(prefijo),
                notas=f"Mapeo de {seccion.replace('#2', '')} (gastos) entregado por Contraloría: "
                "Seniority Premium y Education Bonus",
            )
            db.commit()
            if r.version_numero is None:
                print(f"{seccion}: nada que hacer ({len(r.ya_estaban)} vínculos ya estaban).")
                continue
            print(
                f"{seccion}: mapeo v{r.version_numero} aprobado, {len(r.agregados)} vínculos nuevos."
            )
            for texto in r.agregados:
                print(f"  + {texto}".replace("→", "->"))


if __name__ == "__main__":
    main()
