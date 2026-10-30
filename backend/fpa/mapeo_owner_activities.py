"""Vincula a «Owner Activities» las cuentas de Actividades de Propietarios (6003) que le faltaban
(solo DESARROLLO).

Uso (desde backend/, con la base ya migrada):

    set FPA_ENTORNO=desarrollo
    .venv\\Scripts\\python -m fpa.mapeo_owner_activities

Es el mismo trámite que `mapeo_accounting`, con el mapeo que Contraloría entregó (hoja
`PESO COMPARATIVO MZT` de «Mapeo de Cuentas Mazatlan (1).xlsx») comparado con el aprobado: solo
faltaban dos líneas. Crea y aprueba una versión nueva del mapeo (la anterior se conserva) y es seguro repetirlo. Las demás cuentas 6003 con movimientos que ninguna línea recoge (6003001.013, 6003005,
6003007.x) quedan sin vincular hasta que Contraloría las asigne.
"""

from __future__ import annotations

from sqlalchemy import select

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.vincular_cuentas import VinculoPedido, vincular_cuentas

SECCION = "Owner Activities"

# (línea de la sección, cuenta). La línea que el mapeo de Contraloría llama «Severance Pay» se llama
# «Education Bonus» en la hoja del reporte (misma posición y mismo código corporativo
# 028-0101-60010-000); el Excel escribe 6003001.01 para la prima de antigüedad: es 6003001.010 en el
# catálogo (Excel pierde el cero final).
PEDIDOS: tuple[VinculoPedido, ...] = (
    VinculoPedido("Seniority Premium", "6003001.010"),
    VinculoPedido("Education Bonus", "6003001.011"),
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
            notas="Mapeo de Owner Activities entregado por Contraloría: Seniority Premium y Education Bonus",
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
