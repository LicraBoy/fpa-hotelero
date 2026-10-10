"""Vincula a «Mgmt & Check In» las cuentas de Gerencia y Recepción (6009) (solo DESARROLLO).

Uso (desde backend/, con la base ya migrada):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.mapeo_mgmt_checkin

Es el mapeo que Contraloría entregó (línea → cuentas) comparado con el aprobado: agrega a cada línea
las cuentas que le faltaban y quita la exclusión «a propósito» de 6009001.004 (Holidays) y 6009020
(Equipment), que ahora sí tienen línea. Las cuentas que el catálogo corporativo marca en rojo
«No se utiliza» (#N/D) se **ponen**, pero con esa nota visible en el desglose del reporte. Crea y
aprueba una versión nueva del mapeo (la anterior se conserva) y es seguro repetirlo.
"""

from __future__ import annotations

from sqlalchemy import select

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.vincular_cuentas import VinculoPedido, vincular_cuentas

SECCION = "Mgmt & Check In"
NOTA_NO_SE_UTILIZA = "No se utiliza (catálogo corporativo: #N/D)"

# (línea de la sección, cuenta, nota). Los nombres son los de la estructura del reporte; la línea
# que el mapeo de Contraloría llama «Severance Pay» se llama «Education Bonus» en la hoja del
# reporte (misma posición y mismo código corporativo 028-0111-60010-000).
PEDIDOS: tuple[VinculoPedido, ...] = (
    VinculoPedido("Vacation Bonus", "6009001.003"),
    VinculoPedido("Holidays", "6009001.004"),
    VinculoPedido("Overtime", "6009001.006"),
    VinculoPedido("Compensation", "6009001.007"),
    VinculoPedido("Profit Sharing", "6009001.008"),
    VinculoPedido("Seniority Premium", "6009001.010"),
    VinculoPedido("Education Bonus", "6009001.011"),
    VinculoPedido("Training", "6009009.002"),
    VinculoPedido("Mileage, Taxi, Parking", "6009014.004"),
    VinculoPedido("Equipment", "6009020"),
    VinculoPedido("Materials/Supplies", "6009046.024"),
    VinculoPedido("T & E Local", "6009046.001"),
    VinculoPedido("Postage", "6009027"),
    # catálogo corporativo en rojo: «No se utiliza»
    VinculoPedido("Postage", "6009028", NOTA_NO_SE_UTILIZA),
    VinculoPedido("Insurance", "6009030", NOTA_NO_SE_UTILIZA),
    VinculoPedido("Non-Deductible", "6009043", NOTA_NO_SE_UTILIZA),
    VinculoPedido("Meals & Entertain", "6009012", NOTA_NO_SE_UTILIZA),
    VinculoPedido("Other Fringe", "6009010.004", NOTA_NO_SE_UTILIZA),
    VinculoPedido("Allocated Expenses", "6009084", NOTA_NO_SE_UTILIZA),
    VinculoPedido("Allocated Expenses", "6009085", NOTA_NO_SE_UTILIZA),
    # el Excel escribe 6009085.15: en el catálogo es 6009085.150 (Excel pierde el cero final)
    VinculoPedido("Allocated Expenses", "6009085.150", NOTA_NO_SE_UTILIZA),
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
        r = vincular_cuentas(
            db,
            organizacion_id=hotel.organizacion_id,
            hotel_id=hotel.id,
            editor_id=analista.id,
            aprobador_id=contralor.id,
            seccion=SECCION,
            pedidos=PEDIDOS,
            notas="Mapeo de Mgmt & Check In entregado por Contraloría; las cuentas en rojo del "
            "catálogo corporativo se anotan «No se utiliza»",
        )
        db.commit()
    if r.version_numero is None:
        print(f"Nada que hacer: los {len(r.ya_estaban)} vínculos ya estaban.")
        return
    print(f"Mapeo v{r.version_numero} aprobado: {len(r.agregados)} vínculos nuevos.")
    for texto in r.agregados:
        print(f"  + {texto}".replace("→", "->"))
    if r.exclusiones_quitadas:
        print(f"Dejan de estar excluidas: {', '.join(r.exclusiones_quitadas)}")


if __name__ == "__main__":
    main()
