"""Omite cuentas del reporte (solo DESARROLLO): crea y aprueba una versión nueva del mapeo.

Uso (desde backend/, con la base ya migrada):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.mapeo_omitir 6009020 6009001.004 6006012.001

Contraloría decidió que estas cuentas **todavía no se ocupan**: tienen movimientos pero no entran a
ninguna línea del reporte. Una versión aprobada del mapeo no se edita, así que se copia en un
borrador, se registran las exclusiones (con su motivo y quién) y se aprueba. Es seguro repetirlo.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.omitir_cuentas import MOTIVO_NO_SE_OCUPAN, omitir_cuentas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cuentas", nargs="+", help="Códigos de cuenta a omitir")
    parser.add_argument("--motivo", default=MOTIVO_NO_SE_OCUPAN)
    args = parser.parse_args()
    if settings.entorno != "desarrollo":
        raise SystemExit("Este script solo corre con FPA_ENTORNO=desarrollo.")
    with SessionLocal() as db:
        hotel = sembrar_torres(db)
        db.commit()
        analista = db.scalar(select(Usuario).where(Usuario.email == "analista@torres.local"))
        contralor = db.scalar(select(Usuario).where(Usuario.email == "contralor@torres.local"))
        if analista is None or contralor is None:
            raise SystemExit("Faltan los usuarios de desarrollo: corre `python -m fpa.semilla`")
        r = omitir_cuentas(
            db,
            organizacion_id=hotel.organizacion_id,
            hotel_id=hotel.id,
            editor_id=analista.id,
            aprobador_id=contralor.id,
            cuentas=args.cuentas,
            motivo=args.motivo,
        )
        db.commit()
    if r.version_numero is None:
        print(f"Nada que hacer: ya estaban omitidas ({', '.join(r.ya_estaban)}).")
    else:
        print(f"Mapeo v{r.version_numero} aprobado. Omitidas a propósito: {', '.join(r.omitidas)}")


if __name__ == "__main__":
    main()
