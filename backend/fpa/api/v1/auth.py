"""Inicio y cierre de sesión, cambio de contraseña y segundo factor (ADR 0005).

Reglas:
- Usuario o contraseña incorrectos dan **la misma respuesta** exista o no la cuenta.
- Tras `login_max_intentos` fallos seguidos la cuenta se bloquea `login_bloqueo_min` minutos.
- La contraseña nunca se devuelve ni se registra; solo su hash vive en la base.
- Lo que debe quedar escrito aunque la respuesta sea un error se confirma (`commit`) antes de
  responder, porque `get_db` deshace la transacción cuando hay una excepción.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import obtener_proveedor, principal_actual
from fpa.identidad.principal import Principal
from fpa.identidad.proveedor import ProveedorIdentidad, principal_de_usuario
from fpa.modelos.base import ahora_utc
from fpa.modelos.identidad import Sesion, Usuario
from fpa.seguridad.credenciales import (
    codigo_totp_valido,
    errores_de_politica,
    hashear,
    necesita_nuevo_hash,
    nuevo_secreto_totp,
    uri_totp,
    verificar,
)
from fpa.seguridad.sesiones import crear_sesion, revocar, revocar_todas, sesion_vigente
from fpa.servicios.auditoria import auditar

router = APIRouter(prefix="/auth", tags=["auth"])

MENSAJE_CREDENCIALES = "Usuario, contraseña o código incorrectos"


class LoginEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)
    codigo: str | None = Field(default=None, max_length=12)


class UsuarioSesion(BaseModel):
    usuario_id: int
    email: str
    nombre: str
    roles_por_hotel: dict[int, str]
    totp_activo: bool
    debe_cambiar_password: bool
    # El rol exige segundo factor y el usuario todavía no lo activó
    debe_activar_mfa: bool


class EstadoAuth(BaseModel):
    entorno: str
    autenticado: bool
    usuario: UsuarioSesion | None = None


class CambioPassword(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=1, max_length=200)


class MfaIniciada(BaseModel):
    secreto: str
    uri: str


class CodigoMfa(BaseModel):
    codigo: str = Field(min_length=1, max_length=12)


class ConfirmarPassword(BaseModel):
    password: str = Field(min_length=1, max_length=200)


def _resumen(db: Session, usuario: Usuario) -> UsuarioSesion:
    roles = principal_de_usuario(db, usuario).roles_por_hotel
    exige_mfa = any(rol in settings.mfa_roles_obligatorios for rol in roles.values())
    return UsuarioSesion(
        usuario_id=usuario.id,
        email=usuario.email,
        nombre=usuario.nombre,
        roles_por_hotel=roles,
        totp_activo=usuario.totp_activo,
        debe_cambiar_password=usuario.debe_cambiar_password,
        debe_activar_mfa=exige_mfa and not usuario.totp_activo,
    )


def _poner_cookie(respuesta: Response, token: str) -> None:
    respuesta.set_cookie(
        key=settings.cookie_nombre,
        value=token,
        max_age=settings.sesion_maxima_h * 3600,
        httponly=True,
        secure=settings.cookie_segura,
        samesite="strict",
        path="/api",
    )


def _quitar_cookie(respuesta: Response) -> None:
    respuesta.delete_cookie(
        key=settings.cookie_nombre,
        path="/api",
        httponly=True,
        secure=settings.cookie_segura,
        samesite="strict",
    )


def _fallar(db: Session, usuario: Usuario | None, request: Request) -> None:
    """Registra un intento fallido (y bloquea si toca) y responde 401. Siempre lanza."""
    if usuario is not None:
        usuario.intentos_fallidos += 1
        accion = "auth.login_fallido"
        detalle: dict[str, object] = {"intentos": usuario.intentos_fallidos}
        if usuario.intentos_fallidos >= settings.login_max_intentos:
            usuario.bloqueado_hasta = ahora_utc() + timedelta(minutes=settings.login_bloqueo_min)
            usuario.intentos_fallidos = 0
            accion = "auth.cuenta_bloqueada"
            detalle = {"minutos": settings.login_bloqueo_min}
        auditar(
            db,
            organizacion_id=usuario.organizacion_id,
            hotel_id=None,
            usuario_id=usuario.id,
            accion=accion,
            entidad="usuario",
            entidad_id=usuario.id,
            detalle=detalle,
        )
    db.commit()
    raise HTTPException(status_code=401, detail=MENSAJE_CREDENCIALES)


@router.get("/estado", response_model=EstadoAuth)
def estado(
    request: Request,
    db: Session = Depends(get_db),
    proveedor: ProveedorIdentidad = Depends(obtener_proveedor),
) -> EstadoAuth:
    """Para la pantalla de entrada: en qué entorno está y si ya hay sesión (sin exigirla)."""
    principal = proveedor.autenticar(request, db)
    usuario = db.get(Usuario, principal.usuario_id) if principal else None
    return EstadoAuth(
        entorno=settings.entorno,
        autenticado=usuario is not None,
        usuario=_resumen(db, usuario) if usuario else None,
    )


@router.post("/login", response_model=UsuarioSesion)
def login(
    entrada: LoginEntrada,
    request: Request,
    respuesta: Response,
    db: Session = Depends(get_db),
) -> UsuarioSesion:
    email = entrada.email.strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    ahora = ahora_utc()
    if usuario is not None and usuario.bloqueado_hasta is not None:
        hasta = usuario.bloqueado_hasta
        if (hasta if hasta.tzinfo else hasta.replace(tzinfo=ahora.tzinfo)) > ahora:
            raise HTTPException(
                status_code=429,
                detail="La cuenta está bloqueada temporalmente por intentos fallidos. "
                "Espera unos minutos o pide al contralor que la desbloquee.",
            )
    correcta = verificar(usuario.password_hash if usuario else None, entrada.password)
    if usuario is None or not usuario.activo or not correcta:
        _fallar(db, usuario, request)
        raise AssertionError("inalcanzable")  # _fallar siempre lanza
    if usuario.totp_activo:
        if not entrada.codigo:
            raise HTTPException(status_code=401, detail="Falta el código de verificación")
        if not codigo_totp_valido(usuario.totp_secreto, entrada.codigo):
            _fallar(db, usuario, request)
    # Entró: se limpia el contador, se renueva el hash si cambió el costo y se abre sesión
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    if usuario.password_hash and necesita_nuevo_hash(usuario.password_hash):
        usuario.password_hash = hashear(entrada.password)
    token, sesion = crear_sesion(db, usuario, request.headers.get("user-agent"))
    auditar(
        db,
        organizacion_id=usuario.organizacion_id,
        hotel_id=None,
        usuario_id=usuario.id,
        accion="auth.login",
        entidad="sesion",
        entidad_id=sesion.id,
        detalle={"mfa": usuario.totp_activo},
    )
    db.commit()
    _poner_cookie(respuesta, token)
    return _resumen(db, usuario)


@router.post("/logout", status_code=204)
def logout(request: Request, respuesta: Response, db: Session = Depends(get_db)) -> Response:
    """Cierra la sesión de este navegador (si la hay) y borra la cookie."""
    sesion = sesion_vigente(db, request.cookies.get(settings.cookie_nombre))
    if sesion is not None:
        usuario = db.get(Usuario, sesion.usuario_id)
        revocar(db, sesion)
        if usuario is not None:
            auditar(
                db,
                organizacion_id=usuario.organizacion_id,
                hotel_id=None,
                usuario_id=usuario.id,
                accion="auth.logout",
                entidad="sesion",
                entidad_id=sesion.id,
            )
    db.commit()
    respuesta.status_code = 204
    _quitar_cookie(respuesta)
    return respuesta


def _usuario_del_principal(db: Session, principal: Principal) -> Usuario:
    usuario = db.get(Usuario, principal.usuario_id)
    if usuario is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return usuario


@router.post("/cambiar-password", status_code=204)
def cambiar_password(
    entrada: CambioPassword,
    request: Request,
    principal: Annotated[Principal, Depends(principal_actual)],
    db: Session = Depends(get_db),
) -> None:
    usuario = _usuario_del_principal(db, principal)
    if not verificar(usuario.password_hash, entrada.actual):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    motivos = errores_de_politica(entrada.nueva, usuario.email)
    if motivos:
        raise HTTPException(status_code=422, detail="; ".join(motivos))
    if verificar(usuario.password_hash, entrada.nueva):
        raise HTTPException(status_code=422, detail="La contraseña nueva debe ser distinta")
    usuario.password_hash = hashear(entrada.nueva)
    usuario.password_cambiada_en = ahora_utc()
    usuario.debe_cambiar_password = False
    cerradas = revocar_todas(db, usuario.id, excepto=getattr(request.state, "sesion_id", None))
    auditar(
        db,
        organizacion_id=usuario.organizacion_id,
        hotel_id=None,
        usuario_id=usuario.id,
        accion="auth.password_cambiada",
        entidad="usuario",
        entidad_id=usuario.id,
        detalle={"sesiones_cerradas": cerradas},
    )
    db.commit()


@router.post("/mfa/iniciar", response_model=MfaIniciada)
def iniciar_mfa(
    principal: Annotated[Principal, Depends(principal_actual)], db: Session = Depends(get_db)
) -> MfaIniciada:
    """Genera un secreto nuevo para la app de autenticación; no queda activo hasta confirmarlo."""
    usuario = _usuario_del_principal(db, principal)
    if usuario.totp_activo:
        raise HTTPException(status_code=409, detail="El segundo factor ya está activo")
    usuario.totp_secreto = nuevo_secreto_totp()
    auditar(
        db,
        organizacion_id=usuario.organizacion_id,
        hotel_id=None,
        usuario_id=usuario.id,
        accion="auth.mfa_iniciado",
        entidad="usuario",
        entidad_id=usuario.id,
    )
    db.commit()
    return MfaIniciada(
        secreto=usuario.totp_secreto, uri=uri_totp(usuario.totp_secreto, usuario.email)
    )


@router.post("/mfa/confirmar", status_code=204)
def confirmar_mfa(
    entrada: CodigoMfa,
    principal: Annotated[Principal, Depends(principal_actual)],
    db: Session = Depends(get_db),
) -> None:
    usuario = _usuario_del_principal(db, principal)
    if usuario.totp_activo or not usuario.totp_secreto:
        raise HTTPException(status_code=409, detail="No hay un segundo factor por confirmar")
    if not codigo_totp_valido(usuario.totp_secreto, entrada.codigo):
        raise HTTPException(status_code=422, detail="El código no es correcto")
    usuario.totp_activo = True
    auditar(
        db,
        organizacion_id=usuario.organizacion_id,
        hotel_id=None,
        usuario_id=usuario.id,
        accion="auth.mfa_activado",
        entidad="usuario",
        entidad_id=usuario.id,
    )
    db.commit()


@router.post("/mfa/desactivar", status_code=204)
def desactivar_mfa(
    entrada: ConfirmarPassword,
    principal: Annotated[Principal, Depends(principal_actual)],
    db: Session = Depends(get_db),
) -> None:
    usuario = _usuario_del_principal(db, principal)
    if not verificar(usuario.password_hash, entrada.password):
        raise HTTPException(status_code=400, detail="La contraseña no es correcta")
    usuario.totp_activo = False
    usuario.totp_secreto = None
    auditar(
        db,
        organizacion_id=usuario.organizacion_id,
        hotel_id=None,
        usuario_id=usuario.id,
        accion="auth.mfa_desactivado",
        entidad="usuario",
        entidad_id=usuario.id,
    )
    db.commit()


__all__ = ["Sesion", "router"]
