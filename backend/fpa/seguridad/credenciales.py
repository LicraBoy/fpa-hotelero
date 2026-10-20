"""Contraseñas (argon2id) y segundo factor (TOTP) de los usuarios locales.

La plataforma guarda **solo el hash** de la contraseña (`argon2id`, parámetros por defecto de
`argon2-cffi`, que siguen la recomendación RFC 9106). El secreto TOTP se guarda en la base de datos
tal cual (base32): protege la base con los permisos del sistema operativo; cifrarlo con una llave de
la aplicación queda como mejora `[POR VALIDAR con TI]` (ADR 0005).
"""

from __future__ import annotations

import re

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from fpa.config import settings

_HASHER = PasswordHasher()
# Hash de relleno: se verifica contra él cuando el usuario no existe, para que responder
# «contraseña incorrecta» tarde lo mismo exista o no la cuenta.
_HASH_RELLENO = _HASHER.hash("relleno-que-nadie-conoce-0")

EMISOR_TOTP = "Plataforma FP&A Hotelera"
_COMUNES = {
    "contraseña",
    "contrasena",
    "password",
    "123456789",
    "1234567890",
    "qwerty123",
    "admin12345",
}


def hashear(contrasena: str) -> str:
    return _HASHER.hash(contrasena)


def verificar(hash_guardado: str | None, contrasena: str) -> bool:
    """Compara sin lanzar errores; sin hash guardado usa el de relleno y devuelve falso."""
    objetivo = hash_guardado or _HASH_RELLENO
    try:
        correcta = _HASHER.verify(objetivo, contrasena)
    except (VerificationError, InvalidHashError):
        return False
    return bool(correcta) and hash_guardado is not None


def necesita_nuevo_hash(hash_guardado: str) -> bool:
    return _HASHER.check_needs_rehash(hash_guardado)


def errores_de_politica(contrasena: str, email: str) -> list[str]:
    """Reglas mínimas: largo, letra y número, y nada obvio. Devuelve los motivos de rechazo."""
    errores: list[str] = []
    if len(contrasena) < settings.password_min_largo:
        errores.append(f"Debe tener al menos {settings.password_min_largo} caracteres")
    if len(contrasena) > 200:
        errores.append("Debe tener como máximo 200 caracteres")
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", contrasena):
        errores.append("Debe incluir al menos una letra")
    if not re.search(r"\d", contrasena):
        errores.append("Debe incluir al menos un número")
    usuario = email.split("@")[0].lower()
    if len(usuario) >= 4 and usuario in contrasena.lower():
        errores.append("No debe contener tu usuario")
    if contrasena.lower() in _COMUNES:
        errores.append("Es una contraseña demasiado común")
    return errores


# --- Segundo factor (TOTP) -------------------------------------------------------------------


def nuevo_secreto_totp() -> str:
    return pyotp.random_base32()


def uri_totp(secreto: str, email: str) -> str:
    return pyotp.TOTP(secreto).provisioning_uri(name=email, issuer_name=EMISOR_TOTP)


def codigo_totp_valido(secreto: str | None, codigo: str | None) -> bool:
    """Seis dígitos del momento actual (con una ventana de ±30 s por el reloj del teléfono)."""
    if not secreto or not codigo:
        return False
    limpio = codigo.replace(" ", "")
    if not re.fullmatch(r"\d{6}", limpio):
        return False
    return bool(pyotp.TOTP(secreto).verify(limpio, valid_window=1))
