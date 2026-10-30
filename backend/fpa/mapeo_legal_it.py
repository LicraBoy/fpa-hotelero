"""Vincula a «Legal» e «IT Systems» las cuentas que Contraloría les asigna y faltaban (solo
DESARROLLO).

Uso (desde backend/, con la base ya migrada):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.mapeo_legal_it

Mismo trámite que `mapeo_accounting`: en las dos secciones solo faltaban Seniority Premium (el Excel
escribe
`….01`, que en el catálogo es `….010`) y Education Bonus (que el mapeo de Contraloría llama
«Severance Pay»).
Crea una versión del mapeo por sección y es seguro repetirlo.
"""

from __future__ import annotations

from sqlalchemy import select

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.vincular_cuentas import VinculoPedido, vincular_cuentas

# (sección, prefijo de las cuentas de nómina del departamento)
SECCIONES: tuple[tuple[str, str], ...] = (("Legal", "6001001"), ("IT Systems", "6021001"))


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
        for seccion, prefijo in SECCIONES:
            r = vincular_cuentas(
                db,
                organizacion_id=hotel.organizacion_id,
                hotel_id=hotel.id,
                editor_id=analista.id,
                aprobador_id=contralor.id,
                seccion=seccion,
                pedidos=pedidos_de(prefijo),
                notas=f"Mapeo de {seccion} entregado por Contraloría: Seniority Premium y Education Bonus",
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
