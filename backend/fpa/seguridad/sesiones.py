"""Sesiones del lado del servidor.

El navegador recibe un token opaco en una cookie `HttpOnly; SameSite=Strict`; la base guarda solo su
SHA-256, así que una copia de la base no permite entrar. Una sesión caduca por **inactividad**
(`sesion_inactividad_min`) y por **duración máxima** (`sesion_maxima_h`), y se puede revocar en
cualquier momento (cerrar sesión, cambio de contraseña, administración).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.modelos.base import ahora_utc
from fpa.modelos.identidad import Sesion, Usuario

# La inactividad solo se renueva si pasó al menos esto: así no se escribe en cada petición.
_RENOVAR_CADA = timedelta(minutes=1)


def _utc(momento: datetime) -> datetime:
    """SQLite devuelve fechas sin zona horaria: se interpretan como UTC (así se guardan)."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def hash_de_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def crear_sesion(db: Session, usuario: Usuario, agente: str | None = None) -> tuple[str, Sesion]:
    """Abre una sesión nueva. Devuelve el token (solo existe aquí) y la fila guardada."""
    token = secrets.token_urlsafe(32)
    ahora = ahora_utc()
    sesion = Sesion(
        usuario_id=usuario.id,
        token_hash=hash_de_token(token),
        creada_en=ahora,
        ultimo_uso=ahora,
        expira_en=ahora + timedelta(hours=settings.sesion_maxima_h),
        agente=(agente or "")[:200] or None,
    )
    db.add(sesion)
    db.flush()
    return token, sesion


def sesion_vigente(db: Session, token: str | None) -> Sesion | None:
    """La sesión de ese token si sigue viva (no revocada, no caducada, usuario activo)."""
    if not token:
        return None
    sesion = db.scalar(select(Sesion).where(Sesion.token_hash == hash_de_token(token)))
    if sesion is None or sesion.revocada_en is not None:
        return None
    ahora = ahora_utc()
    if _utc(sesion.expira_en) <= ahora:
        return None
    inactividad = timedelta(minutes=settings.sesion_inactividad_min)
    if _utc(sesion.ultimo_uso) + inactividad <= ahora:
        return None
    usuario = db.get(Usuario, sesion.usuario_id)
    if usuario is None or not usuario.activo:
        return None
    if ahora - _utc(sesion.ultimo_uso) >= _RENOVAR_CADA:
        sesion.ultimo_uso = ahora
        db.commit()
    return sesion


def revocar(db: Session, sesion: Sesion) -> None:
    if sesion.revocada_en is None:
        sesion.revocada_en = ahora_utc()
        db.flush()


def revocar_todas(db: Session, usuario_id: int, *, excepto: int | None = None) -> int:
    """Cierra todas las sesiones abiertas de un usuario (salvo una). Devuelve cuántas cerró."""
    consulta = update(Sesion).where(Sesion.usuario_id == usuario_id, Sesion.revocada_en.is_(None))
    if excepto is not None:
        consulta = consulta.where(Sesion.id != excepto)
    resultado = db.execute(consulta.values(revocada_en=ahora_utc()))
    return int(getattr(resultado, "rowcount", 0) or 0)
