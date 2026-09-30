"""Proveedores de identidad.

Hoy solo existe el de desarrollo (cabecera `X-Usuario-Dev`). El de producción será OIDC con el
proveedor de identidad de la empresa y MFA `[POR VALIDAR con TI]`; se enchufa implementando el
mismo protocolo, sin tocar el resto de la aplicación.
"""

from typing import Protocol

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.identidad.principal import Principal
from fpa.modelos.identidad import Asignacion, Rol, Usuario

CABECERA_DESARROLLO = "X-Usuario-Dev"


class ProveedorIdentidad(Protocol):
    def autenticar(self, request: Request, db: Session) -> Principal | None: ...


def _principal_de_usuario(db: Session, usuario: Usuario) -> Principal:
    filas = db.execute(
        select(Asignacion.hotel_id, Rol.codigo)
        .join(Rol, Rol.id == Asignacion.rol_id)
        .where(Asignacion.usuario_id == usuario.id)
    ).all()
    return Principal(
        usuario_id=usuario.id,
        email=usuario.email,
        organizacion_id=usuario.organizacion_id,
        roles_por_hotel=dict(filas),
    )


class ProveedorDesarrollo:
    """Solo para desarrollo local y pruebas: identifica al usuario por su correo en una cabecera."""

    def autenticar(self, request: Request, db: Session) -> Principal | None:
        email = request.headers.get(CABECERA_DESARROLLO)
        if not email:
            return None
        usuario = db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
        if usuario is None or not usuario.activo:
            return None
        return _principal_de_usuario(db, usuario)


class ProveedorNoConfigurado:
    """Producción sin OIDC configurado: nadie se autentica (seguro por defecto)."""

    def autenticar(self, request: Request, db: Session) -> Principal | None:
        return None


def crear_proveedor() -> ProveedorIdentidad:
    if settings.entorno == "desarrollo":
        return ProveedorDesarrollo()
    return ProveedorNoConfigurado()
