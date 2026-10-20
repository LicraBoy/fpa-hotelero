"""Administración de usuarios de un hotel (Fase 5.2). Solo quien tiene `usuarios:administrar`.

Reglas:
- Solo se ven y editan usuarios con asignación en ese hotel y de la misma organización.
- Un hotel nunca se queda sin un Contralor activo; nadie se desactiva ni se quita el rol a sí mismo.
- Las secciones asignadas solo cuentan para los roles que las usan (responsable de departamento) y
  deben existir en la estructura vigente del reporte.
- Las contraseñas temporales se muestran una sola vez; nunca se guardan ni se registran en claro.
- Cada cambio queda en la bitácora con el antes y el después.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import IdRuta
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado
from fpa.identidad.permisos import NOMBRES_ROL, ROLES_POR_SECCION, Permiso, RolCodigo
from fpa.modelos.base import ahora_utc
from fpa.modelos.identidad import Asignacion, AsignacionDepartamento, Rol, Usuario
from fpa.repositorios.reporte import RepositorioReporte
from fpa.seguridad.credenciales import contrasena_temporal, hashear
from fpa.seguridad.sesiones import revocar_todas
from fpa.semilla import sembrar_roles
from fpa.servicios.auditoria import auditar

router = APIRouter(tags=["usuarios"], responses=RESPUESTAS_HOTEL)

Admin = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.USUARIOS_ADMINISTRAR))]
_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+$")


class UsuarioAdmin(BaseModel):
    usuario_id: int
    email: str
    nombre: str
    rol: str
    rol_nombre: str
    activo: bool
    secciones: list[str]
    totp_activo: bool
    bloqueado: bool
    debe_cambiar_password: bool


class ListaUsuarios(BaseModel):
    usuarios: list[UsuarioAdmin]
    roles: dict[str, str]  # código -> nombre
    roles_por_seccion: list[str]
    secciones_disponibles: list[str]


class UsuarioNuevo(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    nombre: str = Field(min_length=1, max_length=200)
    rol: str
    secciones: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("email")
    @classmethod
    def _correo(cls, v: str) -> str:
        v = v.strip().lower()
        if not _RE_CORREO.match(v):
            raise ValueError("El correo no es válido")
        return v


class CambiosUsuario(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    rol: str | None = None
    activo: bool | None = None
    secciones: list[str] | None = Field(default=None, max_length=100)


class UsuarioCreado(BaseModel):
    usuario: UsuarioAdmin
    # Solo cuando se creó la cuenta: se muestra una vez y no se puede volver a consultar
    password_temporal: str | None


class PasswordTemporal(BaseModel):
    password_temporal: str


def _secciones_del_hotel(db: Session, hotel_id: int) -> list[str]:
    repo = RepositorioReporte(db, hotel_id)
    version = repo.vigente()
    if version is None:
        return []
    return [x.descripcion for x in repo.lineas(version.id) if x.tipo == "seccion"]


def _fila(db: Session, hotel_id: int, usuario: Usuario, rol: str) -> UsuarioAdmin:
    secciones = sorted(
        db.scalars(
            select(AsignacionDepartamento.seccion).where(
                AsignacionDepartamento.usuario_id == usuario.id,
                AsignacionDepartamento.hotel_id == hotel_id,
            )
        )
    )
    hasta = usuario.bloqueado_hasta
    bloqueado = (
        hasta is not None
        and (hasta if hasta.tzinfo else hasta.replace(tzinfo=ahora_utc().tzinfo)) > ahora_utc()
    )
    return UsuarioAdmin(
        usuario_id=usuario.id,
        email=usuario.email,
        nombre=usuario.nombre,
        rol=rol,
        rol_nombre=NOMBRES_ROL.get(RolCodigo(rol), rol) if rol in RolCodigo else rol,
        activo=usuario.activo,
        secciones=secciones,
        totp_activo=usuario.totp_activo,
        bloqueado=bloqueado,
        debe_cambiar_password=usuario.debe_cambiar_password,
    )


def _asignados(db: Session, contexto: ContextoHotel) -> list[tuple[Usuario, Asignacion, str]]:
    filas = db.execute(
        select(Usuario, Asignacion, Rol.codigo)
        .join(Asignacion, Asignacion.usuario_id == Usuario.id)
        .join(Rol, Rol.id == Asignacion.rol_id)
        .where(
            Asignacion.hotel_id == contexto.hotel_id,
            Usuario.organizacion_id == contexto.organizacion_id,
        )
        .order_by(Usuario.nombre)
    ).all()
    return [(u, a, c) for u, a, c in filas]


def _de_este_hotel(
    db: Session, contexto: ContextoHotel, usuario_id: int
) -> tuple[Usuario, Asignacion, str]:
    for u, a, codigo in _asignados(db, contexto):
        if u.id == usuario_id:
            return u, a, codigo
    raise HTTPException(status_code=404, detail="Usuario no encontrado")


def _rol_valido(db: Session, codigo: str) -> Rol:
    roles = sembrar_roles(db)
    if codigo not in roles:
        raise HTTPException(status_code=422, detail=f"Rol desconocido: {codigo}")
    return roles[codigo]


def _validar_secciones(db: Session, hotel_id: int, secciones: list[str]) -> list[str]:
    disponibles = set(_secciones_del_hotel(db, hotel_id))
    limpias = sorted({x.strip() for x in secciones if x.strip()})
    desconocidas = [x for x in limpias if x not in disponibles]
    if desconocidas:
        raise HTTPException(
            status_code=422,
            detail="Secciones que no existen en el reporte: " + ", ".join(desconocidas),
        )
    return limpias


def _poner_secciones(db: Session, hotel_id: int, usuario_id: int, secciones: list[str]) -> None:
    db.execute(
        delete(AsignacionDepartamento).where(
            AsignacionDepartamento.usuario_id == usuario_id,
            AsignacionDepartamento.hotel_id == hotel_id,
        )
    )
    for nombre in secciones:
        db.add(AsignacionDepartamento(usuario_id=usuario_id, hotel_id=hotel_id, seccion=nombre))


def _contralores_activos(db: Session, contexto: ContextoHotel) -> list[int]:
    return [u.id for u, _, c in _asignados(db, contexto) if c == RolCodigo.CONTRALOR and u.activo]


@router.get("/hoteles/{hotel_id}/usuarios", response_model=ListaUsuarios)
def listar(contexto: Admin, db: Session = Depends(get_db)) -> ListaUsuarios:
    return ListaUsuarios(
        usuarios=[_fila(db, contexto.hotel_id, u, c) for u, _, c in _asignados(db, contexto)],
        roles={r.value: n for r, n in NOMBRES_ROL.items()},
        roles_por_seccion=sorted(r.value for r in ROLES_POR_SECCION),
        secciones_disponibles=_secciones_del_hotel(db, contexto.hotel_id),
    )


@router.post(
    "/hoteles/{hotel_id}/usuarios",
    response_model=UsuarioCreado,
    status_code=201,
    responses={409: {"description": "El usuario ya tiene acceso a este hotel"}},
)
def crear(entrada: UsuarioNuevo, contexto: Admin, db: Session = Depends(get_db)) -> UsuarioCreado:
    rol = _rol_valido(db, entrada.rol)
    secciones = (
        _validar_secciones(db, contexto.hotel_id, entrada.secciones)
        if entrada.rol in ROLES_POR_SECCION
        else []
    )
    usuario = db.scalar(select(Usuario).where(Usuario.email == entrada.email))
    clave: str | None = None
    if usuario is None:
        usuario = Usuario(
            organizacion_id=contexto.organizacion_id, email=entrada.email, nombre=entrada.nombre
        )
        clave = contrasena_temporal()
        usuario.password_hash = hashear(clave)
        usuario.password_cambiada_en = ahora_utc()
        usuario.debe_cambiar_password = True
        db.add(usuario)
        db.flush()
    elif usuario.organizacion_id != contexto.organizacion_id:
        # no se revela que el correo existe en otra organización
        raise HTTPException(status_code=409, detail="No se pudo crear ese usuario")
    existente = db.scalar(
        select(Asignacion).where(
            Asignacion.usuario_id == usuario.id, Asignacion.hotel_id == contexto.hotel_id
        )
    )
    if existente is not None:
        raise HTTPException(status_code=409, detail="Ese usuario ya tiene acceso a este hotel")
    db.add(Asignacion(usuario_id=usuario.id, hotel_id=contexto.hotel_id, rol_id=rol.id))
    _poner_secciones(db, contexto.hotel_id, usuario.id, secciones)
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="usuario.creado" if clave else "usuario.acceso_agregado",
        entidad="usuario",
        entidad_id=usuario.id,
        detalle={"email": usuario.email, "rol": entrada.rol, "secciones": secciones},
    )
    db.commit()
    return UsuarioCreado(
        usuario=_fila(db, contexto.hotel_id, usuario, entrada.rol), password_temporal=clave
    )


@router.patch(
    "/hoteles/{hotel_id}/usuarios/{usuario_id}",
    response_model=UsuarioAdmin,
    responses={409: {"description": "El cambio dejaría al hotel sin un Contralor activo"}},
)
def actualizar(
    usuario_id: IdRuta,
    cambios: CambiosUsuario,
    contexto: Admin,
    db: Session = Depends(get_db),
) -> UsuarioAdmin:
    usuario, asignacion, rol_actual = _de_este_hotel(db, contexto, usuario_id)
    yo = usuario.id == contexto.principal.usuario_id
    antes = _fila(db, contexto.hotel_id, usuario, rol_actual).model_dump()
    rol_nuevo = cambios.rol or rol_actual

    if yo and (rol_nuevo != rol_actual or cambios.activo is False):
        raise HTTPException(
            status_code=409, detail="No puedes quitarte tu propio rol ni desactivarte"
        )
    if cambios.rol is not None and cambios.rol != rol_actual:
        asignacion.rol_id = _rol_valido(db, cambios.rol).id
    if cambios.nombre is not None:
        usuario.nombre = cambios.nombre
    if cambios.activo is not None and cambios.activo != usuario.activo:
        if not cambios.activo:
            ajenos = [
                h
                for h in db.scalars(
                    select(Asignacion.hotel_id).where(Asignacion.usuario_id == usuario.id)
                )
                if contexto.principal.roles_por_hotel.get(h) != RolCodigo.CONTRALOR
            ]
            if ajenos:
                raise HTTPException(
                    status_code=409,
                    detail="Tiene acceso a otros hoteles que no administras: no se puede "
                    "desactivar la cuenta completa",
                )
            revocar_todas(db, usuario.id)
        usuario.activo = cambios.activo
    if rol_nuevo in ROLES_POR_SECCION:
        if cambios.secciones is not None:
            _poner_secciones(
                db,
                contexto.hotel_id,
                usuario.id,
                _validar_secciones(db, contexto.hotel_id, cambios.secciones),
            )
    elif rol_actual in ROLES_POR_SECCION:
        _poner_secciones(db, contexto.hotel_id, usuario.id, [])  # ya no aplican

    db.flush()
    if not _contralores_activos(db, contexto):
        db.rollback()
        raise HTTPException(
            status_code=409, detail="El hotel debe conservar al menos un Contralor activo"
        )
    despues = _fila(db, contexto.hotel_id, usuario, rol_nuevo)
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="usuario.actualizado",
        entidad="usuario",
        entidad_id=usuario.id,
        detalle={
            "antes": {k: antes[k] for k in ("nombre", "rol", "activo", "secciones")},
            "despues": {
                k: despues.model_dump()[k] for k in ("nombre", "rol", "activo", "secciones")
            },
        },
    )
    db.commit()
    return despues


@router.post(
    "/hoteles/{hotel_id}/usuarios/{usuario_id}/restablecer-password",
    response_model=PasswordTemporal,
)
def restablecer_password(
    usuario_id: IdRuta, contexto: Admin, db: Session = Depends(get_db)
) -> PasswordTemporal:
    """Nueva clave temporal (se muestra una vez); cierra sus sesiones y lo obliga a cambiarla."""
    usuario, _, _ = _de_este_hotel(db, contexto, usuario_id)
    clave = contrasena_temporal()
    usuario.password_hash = hashear(clave)
    usuario.password_cambiada_en = ahora_utc()
    usuario.debe_cambiar_password = True
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    cerradas = revocar_todas(db, usuario.id)
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="usuario.password_restablecida",
        entidad="usuario",
        entidad_id=usuario.id,
        detalle={"sesiones_cerradas": cerradas},
    )
    db.commit()
    return PasswordTemporal(password_temporal=clave)


@router.post("/hoteles/{hotel_id}/usuarios/{usuario_id}/desbloquear", status_code=204)
def desbloquear(usuario_id: IdRuta, contexto: Admin, db: Session = Depends(get_db)) -> None:
    usuario, _, _ = _de_este_hotel(db, contexto, usuario_id)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    auditar(
        db,
        organizacion_id=contexto.organizacion_id,
        hotel_id=contexto.hotel_id,
        usuario_id=contexto.principal.usuario_id,
        accion="usuario.desbloqueado",
        entidad="usuario",
        entidad_id=usuario.id,
    )
    db.commit()
