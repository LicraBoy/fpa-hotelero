"""Vincula a «Apartment Interior» las cuentas de Departamentos (6012) que le faltaban (solo DESARROLLO).

Uso (desde backend/, con la base ya migrada):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.mapeo_apartment_interior

Mismo trámite que `mapeo_accounting`, con el mapeo que Contraloría entregó (hoja `PESO COMPARATIVO MZT`
de «Mapeo de Cuentas Mazatlan (1).xlsx») comparado con el aprobado: falta Education Bonus y la cuenta
6012106 (Equipment/Supplies) estaba en la línea «PH» junto a 6012107, cuando Contraloría las separa:
6012106 → «Equipment/Supplies» y 6012107 → «Equip/Supplies PH». Crea y aprueba una versión nueva del
mapeo (la anterior se conserva) y es seguro repetirlo.
"""

from __future__ import annotations

from sqlalchemy import select

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.vincular_cuentas import VinculoPedido, vincular_cuentas

SECCION = "Apartment Interior"

# La línea que el mapeo de Contraloría llama «Severance Pay» es «Education Bonus» en el reporte (misma
# posición y código corporativo 028-0118-60010-000).
PEDIDOS: tuple[VinculoPedido, ...] = (
    VinculoPedido("Education Bonus", "6012001.011"),
    VinculoPedido("Equipment/Supplies", "6012106"),
)
QUITAR: tuple[VinculoPedido, ...] = (VinculoPedido("Equip/Supplies PH", "6012106"),)


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
        r = vincular_cuentas(
            db,
            organizacion_id=hotel.organizacion_id,
            hotel_id=hotel.id,
            editor_id=analista.id,
            aprobador_id=contralor.id,
            seccion=SECCION,
            pedidos=PEDIDOS,
            quitar=QUITAR,
            notas="Mapeo de Apartment Interior entregado por Contraloría: Education Bonus y 6012106 "
            "en Equipment/Supplies (ya no en la línea PH)",
        )
        db.commit()
    if r.version_numero is None:
        print(f"Nada que hacer: los {len(r.ya_estaban)} vínculos ya estaban.")
        return
    print(f"Mapeo v{r.version_numero} aprobado: {len(r.agregados)} vínculos nuevos.")
    for texto in r.agregados:
        print(f"  + {texto}".replace("→", "->"))
    for texto in r.vinculos_quitados:
        print(f"  - {texto}".replace("←", "<-"))
    if r.exclusiones_quitadas:
        print(f"Dejan de estar excluidas: {', '.join(r.exclusiones_quitadas)}")


if __name__ == "__main__":
    main()
