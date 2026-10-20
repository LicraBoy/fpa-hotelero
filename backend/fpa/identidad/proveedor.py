"""Proveedores de identidad.

- **Sesión** (producción): usuarios locales con contraseña `argon2id`, TOTP opcional y una cookie
  de sesión `HttpOnly` que el servidor valida (ADR 0005).
- **Desarrollo** (solo con `FPA_ENTORNO=desarrollo`): cabecera `X-Usuario-Dev`.

Un proveedor nuevo (p. ej. OIDC si TI lo ofrece) se enchufa implementando el mismo protocolo, sin
tocar el resto de la aplicación.
"""

from typing import Protocol

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.identidad.principal import Principal
from fpa.modelos.identidad import Asignacion, Rol, Usuario
from fpa.seguridad.sesiones import sesion_vigente

CABECERA_DESARROLLO = "X-Usuario-Dev"


class ProveedorIdentidad(Protocol):
    def autenticar(self, request: Request, db: Session) -> Principal | None: ...


def principal_de_usuario(db: Session, usuario: Usuario) -> Principal:
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
        return principal_de_usuario(db, usuario)


class ProveedorSesion:
    """Identifica al usuario por su cookie de sesión (token opaco validado en la base)."""

    def autenticar(self, request: Request, db: Session) -> Principal | None:
        sesion = sesion_vigente(db, request.cookies.get(settings.cookie_nombre))
        if sesion is None:
            return None
        usuario = db.get(Usuario, sesion.usuario_id)
        if usuario is None:
            return None
        request.state.sesion_id = sesion.id
        return principal_de_usuario(db, usuario)


class ProveedorCompuesto:
    """Prueba cada proveedor en orden y se queda con el primero que reconoce al usuario."""

    def __init__(self, *proveedores: ProveedorIdentidad) -> None:
        self._proveedores = proveedores

    def autenticar(self, request: Request, db: Session) -> Principal | None:
        for proveedor in self._proveedores:
            principal = proveedor.autenticar(request, db)
            if principal is not None:
                return principal
        return None


def crear_proveedor() -> ProveedorIdentidad:
    # Producción: solo sesión. Desarrollo: sesión o cabecera `X-Usuario-Dev` (para probar el login
    # real sin perder el selector de usuarios de desarrollo).
    if settings.entorno == "desarrollo":
        return ProveedorCompuesto(ProveedorSesion(), ProveedorDesarrollo())
    return ProveedorSesion()
