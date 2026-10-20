"""Validación de archivos subidos (Arquitectura §8.5). Es el punto de entrada más expuesto.

Un .xlsx es un ZIP: además de revisar extensión y tamaño se inspecciona el ZIP sin confiar en lo
que declara (un ZIP puede mentir sobre su tamaño). Nunca se ejecuta ni evalúa el contenido.

Límites medidos con los Excel reales de Torres (razón de compresión máxima ≈ 35, 9.5 MB
descomprimidos, 351 entradas): los de aquí dejan mucho margen a archivos legítimos.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fpa.config import settings

FIRMA_ZIP = b"PK\x03\x04"
_CHUNK = 1024 * 1024
_EXTENSIONES_NO_SOPORTADAS = {
    ".xlsm": "Los archivos con macros (.xlsm) no se aceptan",
    ".xlsb": "El formato .xlsb no está soportado; guarda el libro como .xlsx",
    ".xls": "El formato antiguo .xls no está soportado; guarda el libro como .xlsx",
    ".csv": "Por ahora solo se aceptan libros .xlsx",
}


class ArchivoRechazado(Exception):
    """El archivo no cumple las reglas de seguridad. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


@dataclass(frozen=True)
class LimitesArchivo:
    max_bytes: int
    zip_max_entradas: int
    zip_max_descomprimido: int
    zip_max_razon: int

    @classmethod
    def desde_settings(cls) -> LimitesArchivo:
        return cls(
            max_bytes=settings.carga_max_bytes,
            zip_max_entradas=settings.zip_max_entradas,
            zip_max_descomprimido=settings.zip_max_descomprimido,
            zip_max_razon=settings.zip_max_razon,
        )


def nombre_seguro(nombre: str | None) -> str:
    """Solo para mostrar y registrar: sin rutas ni caracteres de control. Nunca forma una ruta."""
    base = re.split(r"[\\/]", nombre or "archivo")[-1]
    limpio = "".join(c for c in base if c.isprintable()).strip()
    return (limpio or "archivo")[:200]


def verificar_nombre(nombre: str) -> None:
    minusculas = nombre.lower()
    for extension, mensaje in _EXTENSIONES_NO_SOPORTADAS.items():
        if minusculas.endswith(extension):
            raise ArchivoRechazado(415, mensaje)
    if not minusculas.endswith(".xlsx"):
        raise ArchivoRechazado(415, "Solo se aceptan archivos .xlsx")


def guardar_en_temporal(
    origen: BinaryIO, carpeta: Path, limites: LimitesArchivo, sufijo: str = ".xlsx"
) -> tuple[Path, str, int]:
    """Copia por bloques a un temporal de nombre aleatorio. Devuelve (ruta, sha256, bytes)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    # Con .xlsx como sufijo predeterminado: openpyxl se niega a abrir otras extensiones.
    ruta = carpeta / f"{os.urandom(16).hex()}{sufijo}"
    sha = hashlib.sha256()
    total = 0
    try:
        with ruta.open("wb") as destino:
            while True:
                bloque = origen.read(_CHUNK)
                if not bloque:
                    break
                total += len(bloque)
                if total > limites.max_bytes:
                    raise ArchivoRechazado(
                        413,
                        f"El archivo supera el máximo de {limites.max_bytes // (1024 * 1024)} MB",
                    )
                sha.update(bloque)
                destino.write(bloque)
    except BaseException:
        ruta.unlink(missing_ok=True)
        raise
    if total == 0:
        ruta.unlink(missing_ok=True)
        raise ArchivoRechazado(400, "El archivo está vacío")
    return ruta, sha.hexdigest(), total


FIRMA_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")
# Nombre del flujo donde Excel guarda las macros (VBA) dentro de un .xls, en UTF-16
_MARCA_MACROS = "_VBA_PROJECT".encode("utf-16-le")


def verificar_nombre_xls(nombre: str) -> None:
    """El catálogo de Novohit (CON020) se exporta como .xls."""
    minusculas = nombre.lower()
    if minusculas.endswith(".xlsm"):
        raise ArchivoRechazado(415, "Los archivos con macros (.xlsm) no se aceptan")
    if not minusculas.endswith(".xls"):
        raise ArchivoRechazado(
            415, "El catálogo debe cargarse en formato .xls (el que exporta Novohit)"
        )


_EXTENSIONES_CON130 = (".xlsx", ".xls", ".csv")


def verificar_nombre_con130(nombre: str) -> str:
    """El CON130 se acepta como .xlsx, .xls (el de Novohit) o .csv. Devuelve la extensión."""
    minusculas = nombre.lower()
    if minusculas.endswith(".xlsm"):
        raise ArchivoRechazado(415, "Los archivos con macros (.xlsm) no se aceptan")
    if minusculas.endswith(".xlsb"):
        raise ArchivoRechazado(
            415, "El formato .xlsb no está soportado; guarda el libro como .xlsx"
        )
    for extension in _EXTENSIONES_CON130:
        if minusculas.endswith(extension):
            return extension
    raise ArchivoRechazado(415, "Solo se aceptan archivos .xlsx, .xls o .csv")


def inspeccionar_csv(ruta: Path) -> None:
    """Un CSV es texto: rechaza lo binario (p. ej. un Excel renombrado)."""
    with ruta.open("rb") as f:
        inicio = f.read(8192)
    if inicio.startswith((FIRMA_ZIP, FIRMA_OLE2)) or b"\x00" in inicio:
        raise ArchivoRechazado(415, "El contenido no es un archivo CSV de texto")


def inspeccionar_xls(ruta: Path) -> None:
    """Rechaza lo que no sea un libro .xls (OLE2) sano y sin macros. Lanza `ArchivoRechazado`."""
    contenido = ruta.read_bytes()  # ya acotado por el tamaño máximo de la subida
    if contenido[:8] != FIRMA_OLE2:
        raise ArchivoRechazado(415, "El contenido no es un libro de Excel .xls")
    if _MARCA_MACROS in contenido:
        raise ArchivoRechazado(415, "Los libros con macros no se aceptan")


_FIRMAS_EVIDENCIA = {
    ".pdf": b"%PDF-",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}
EXTENSIONES_EVIDENCIA = (*_FIRMAS_EVIDENCIA, ".xlsx")
# Un PDF que ejecuta código o abre programas al verse no es evidencia
_PDF_ACTIVO = (b"/JavaScript", b"/JS", b"/Launch", b"/OpenAction", b"/EmbeddedFile")


def verificar_nombre_evidencia(nombre: str) -> str:
    """Evidencia de un comentario: PDF, imagen (PNG/JPG) o libro .xlsx. Devuelve la extensión."""
    minusculas = nombre.lower()
    if minusculas.endswith(".xlsm"):
        raise ArchivoRechazado(415, "Los archivos con macros (.xlsm) no se aceptan")
    for extension in EXTENSIONES_EVIDENCIA:
        if minusculas.endswith(extension):
            return extension
    raise ArchivoRechazado(415, "Solo se aceptan PDF, imágenes PNG o JPG y libros .xlsx")


def inspeccionar_evidencia(ruta: Path, extension: str, limites: LimitesArchivo) -> None:
    """El contenido debe corresponder a la extensión (no se confía en el nombre)."""
    if extension == ".xlsx":
        inspeccionar_xlsx(ruta, limites)
        return
    with ruta.open("rb") as f:
        inicio = f.read(16)
    if not inicio.startswith(_FIRMAS_EVIDENCIA[extension]):
        raise ArchivoRechazado(415, "El contenido no corresponde al tipo de archivo")
    if extension == ".pdf":
        contenido = ruta.read_bytes()  # acotado por el tamaño máximo de la subida
        if any(marca in contenido for marca in _PDF_ACTIVO):
            raise ArchivoRechazado(415, "El PDF trae contenido activo (scripts o adjuntos)")


def limpiar_temporales(carpeta: Path, edad_maxima_s: float = 3600.0) -> None:
    """Borra temporales huérfanos (p. ej. tras una caída). Si uno está en uso, se omite."""
    if not carpeta.exists():
        return
    limite = time.time() - edad_maxima_s
    for ruta in [*carpeta.glob("*.xlsx"), *carpeta.glob("*.xls"), *carpeta.glob("*.csv")]:
        try:
            if ruta.stat().st_mtime < limite:
                ruta.unlink()
        except OSError:
            continue


def inspeccionar_xlsx(ruta: Path, limites: LimitesArchivo) -> None:
    """Rechaza lo que no sea un libro .xlsx sano. Lanza `ArchivoRechazado`."""
    with ruta.open("rb") as f:
        if f.read(4) != FIRMA_ZIP:
            raise ArchivoRechazado(415, "El contenido no es un libro de Excel (.xlsx)")
    try:
        zf = zipfile.ZipFile(ruta)
    except zipfile.BadZipFile:
        raise ArchivoRechazado(415, "El contenido no es un libro de Excel (.xlsx)") from None
    with zf:
        infos = zf.infolist()
        if len(infos) > limites.zip_max_entradas:
            raise ArchivoRechazado(413, "El libro trae demasiados componentes internos")
        nombres = [i.filename for i in infos]
        for i in infos:
            partes = i.filename.replace("\\", "/").split("/")
            if i.filename.startswith(("/", "\\")) or ".." in partes or ":" in i.filename:
                raise ArchivoRechazado(400, "El libro contiene rutas internas sospechosas")
            if i.flag_bits & 0x1:
                raise ArchivoRechazado(400, "No se aceptan libros protegidos con contraseña")
            sospechosa = (
                i.file_size > _CHUNK
                and i.compress_size > 0
                and i.file_size / i.compress_size > limites.zip_max_razon
            )
            if sospechosa:
                raise ArchivoRechazado(413, "El libro tiene una compresión sospechosa")
        if any("vbaproject" in n.lower() for n in nombres):
            raise ArchivoRechazado(415, "Los libros con macros no se aceptan")
        if "[Content_Types].xml" not in nombres or "xl/workbook.xml" not in nombres:
            raise ArchivoRechazado(415, "El contenido no es un libro de Excel (.xlsx)")
        # Descomprime de verdad (contando bytes reales): el tamaño declarado podría mentir.
        total_real = 0
        for i in infos:
            real = 0
            try:
                with zf.open(i) as parte:
                    while bloque := parte.read(_CHUNK):
                        real += len(bloque)
                        total_real += len(bloque)
                        if total_real > limites.zip_max_descomprimido:
                            raise ArchivoRechazado(
                                413, "El contenido descomprimido es demasiado grande"
                            )
                        if real > i.file_size:
                            raise ArchivoRechazado(400, "El libro declara un tamaño falso")
                        if i.filename == "[Content_Types].xml" and b"macroEnabled" in bloque:
                            raise ArchivoRechazado(415, "Los libros con macros no se aceptan")
            except (zipfile.BadZipFile, RuntimeError, OSError):
                raise ArchivoRechazado(415, "El libro está dañado") from None
            if real != i.file_size:
                raise ArchivoRechazado(400, "El libro declara un tamaño falso")
