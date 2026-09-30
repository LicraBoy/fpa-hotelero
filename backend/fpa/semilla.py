"""Datos iniciales de desarrollo (idempotente). Uso: `python -m fpa.semilla`.

Requiere haber aplicado las migraciones (`alembic upgrade head`).
Crea la organización y el hotel de Torres Mazatlán, los roles y un usuario de desarrollo por rol.
Los correos terminan en `.local`: no son personas reales.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.db import SessionLocal
from fpa.identidad.permisos import NOMBRES_ROL, RolCodigo
from fpa.modelos.identidad import Asignacion, Rol, Usuario
from fpa.modelos.organizacion import Hotel, Organizacion

NOMBRE_ORGANIZACION = "Torres Mazatlan S.A. de C.V."
CODIGO_HOTEL = "TORRES-MZT"
NOMBRE_HOTEL = "Torres Mazatlán"

USUARIOS_DESARROLLO = {
    "contralor@torres.local": ("Contralor (desarrollo)", RolCodigo.CONTRALOR),
    "analista@torres.local": ("Analista (desarrollo)", RolCodigo.ANALISTA),
    "responsable@torres.local": ("Responsable de área (desarrollo)", RolCodigo.RESPONSABLE_AREA),
    "direccion@torres.local": ("Dirección (desarrollo)", RolCodigo.DIRECCION),
    "auditoria@torres.local": ("Auditoría (desarrollo)", RolCodigo.AUDITORIA),
}


def sembrar_roles(db: Session) -> dict[str, Rol]:
    existentes = {r.codigo: r for r in db.scalars(select(Rol))}
    for codigo, nombre in NOMBRES_ROL.items():
        if codigo.value not in existentes:
            rol = Rol(codigo=codigo.value, nombre=nombre)
            db.add(rol)
            existentes[codigo.value] = rol
    db.flush()
    return existentes


def sembrar_torres(db: Session) -> Hotel:
    roles = sembrar_roles(db)
    org = db.scalar(select(Organizacion).where(Organizacion.nombre == NOMBRE_ORGANIZACION))
    if org is None:
        org = Organizacion(nombre=NOMBRE_ORGANIZACION)
        db.add(org)
        db.flush()
    hotel = db.scalar(
        select(Hotel).where(Hotel.organizacion_id == org.id, Hotel.codigo == CODIGO_HOTEL)
    )
    if hotel is None:
        hotel = Hotel(organizacion_id=org.id, codigo=CODIGO_HOTEL, nombre=NOMBRE_HOTEL)
        db.add(hotel)
        db.flush()
    for email, (nombre, rol) in USUARIOS_DESARROLLO.items():
        usuario = db.scalar(select(Usuario).where(Usuario.email == email))
        if usuario is None:
            usuario = Usuario(organizacion_id=org.id, email=email, nombre=nombre)
            db.add(usuario)
            db.flush()
        asignada = db.scalar(
            select(Asignacion).where(
                Asignacion.usuario_id == usuario.id, Asignacion.hotel_id == hotel.id
            )
        )
        if asignada is None:
            db.add(Asignacion(usuario_id=usuario.id, hotel_id=hotel.id, rol_id=roles[rol.value].id))
    db.flush()
    return hotel


def main() -> None:
    with SessionLocal() as db:
        hotel = sembrar_torres(db)
        db.commit()
        total = len(USUARIOS_DESARROLLO)
        print(f"Listo: hotel '{hotel.nombre}' (id {hotel.id}) con {total} usuarios.")
        for email in USUARIOS_DESARROLLO:
            print(f"  - {email}")


if __name__ == "__main__":
    main()
