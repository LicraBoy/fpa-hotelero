"""Crea el primer usuario real (o restablece la contraseña de uno existente) sin pantalla de admin.

Uso (desde backend/):
    .venv\\Scripts\\python scripts/crear_contralor.py --email a@b.com --nombre "Nombre"
    .venv\\Scripts\\python scripts/crear_contralor.py --email a@b.com --restablecer

Imprime una contraseña temporal UNA sola vez; el sistema obliga a cambiarla al entrar. Si no se
indica otra cosa, el usuario queda como Contralor del hotel con código `MZT` (Torres Mazatlán).
"""

import argparse
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from fpa.db import SessionLocal
from fpa.modelos import Asignacion, Hotel, Usuario
from fpa.modelos.base import ahora_utc
from fpa.seguridad.credenciales import hashear
from fpa.seguridad.sesiones import revocar_todas
from fpa.semilla import CODIGO_HOTEL, sembrar_roles


def contrasena_temporal() -> str:
    alfabeto = string.ascii_letters + string.digits
    cuerpo = "".join(secrets.choice(alfabeto) for _ in range(14))
    return f"{cuerpo[:7]}-{cuerpo[7:]}1a"  # siempre trae letras y número


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--email", required=True, help="usuario de entrada (correo)")
    ap.add_argument("--nombre", help="nombre completo (obligatorio si el usuario es nuevo)")
    ap.add_argument("--rol", default="contralor", help="código del rol (por defecto: contralor)")
    ap.add_argument("--hotel", default=CODIGO_HOTEL, help="código del hotel")
    ap.add_argument("--restablecer", action="store_true", help="solo cambia la contraseña")
    args = ap.parse_args()
    email = args.email.strip().lower()

    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.email == email))
        if usuario is None:
            if args.restablecer or not args.nombre:
                print("El usuario no existe: indica --nombre para crearlo.", file=sys.stderr)
                return 1
            hotel = db.scalar(select(Hotel).where(Hotel.codigo == args.hotel))
            if hotel is None:
                print(f"No existe el hotel '{args.hotel}'. ¿Corriste la semilla?", file=sys.stderr)
                return 1
            roles = sembrar_roles(db)
            if args.rol not in roles:
                print(
                    f"Rol desconocido '{args.rol}'. Opciones: {', '.join(roles)}", file=sys.stderr
                )
                return 1
            usuario = Usuario(
                organizacion_id=hotel.organizacion_id, email=email, nombre=args.nombre
            )
            db.add(usuario)
            db.flush()
            db.add(Asignacion(usuario_id=usuario.id, hotel_id=hotel.id, rol_id=roles[args.rol].id))
            print(f"Usuario creado: {email} ({args.rol} en {hotel.nombre})")
        clave = contrasena_temporal()
        usuario.password_hash = hashear(clave)
        usuario.password_cambiada_en = ahora_utc()
        usuario.debe_cambiar_password = True
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        usuario.activo = True
        cerradas = revocar_todas(db, usuario.id)
        db.commit()
    print(f"Contraseña temporal (anótala, no se vuelve a mostrar): {clave}")
    if cerradas:
        print(f"Se cerraron {cerradas} sesiones abiertas de ese usuario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
