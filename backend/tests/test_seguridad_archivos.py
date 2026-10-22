"""Pruebas de `escanear_antivirus` (ADR 0011). Sin `clamd` real en esta máquina: se mockea el
cliente para probar los tres caminos (limpio, infectado, clamd no disponible)."""

from __future__ import annotations

from pathlib import Path

import clamd
import pytest

from fpa.seguridad import archivos
from fpa.seguridad.archivos import ArchivoRechazado, escanear_antivirus


@pytest.fixture
def archivo_temporal(tmp_path: Path) -> Path:
    ruta = tmp_path / "prueba.xlsx"
    ruta.write_bytes(b"contenido de prueba")
    return ruta


def test_apagado_no_escanea(archivo_temporal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archivos.settings, "clamav_activo", False)

    def _no_debe_llamarse(*args: object, **kwargs: object) -> None:
        raise AssertionError("no debe conectarse a clamd si FPA_CLAMAV_ACTIVO=false")

    monkeypatch.setattr(clamd, "ClamdNetworkSocket", _no_debe_llamarse)
    escanear_antivirus(archivo_temporal)  # no lanza nada


class _ClienteFalso:
    def __init__(
        self,
        resultado: dict[str, tuple[str, str]] | None = None,
        lanza: Exception | None = None,
    ):
        self._resultado = resultado
        self._lanza = lanza

    def scan(self, ruta: str) -> dict[str, tuple[str, str]] | None:
        if self._lanza:
            raise self._lanza
        return self._resultado


def test_archivo_limpio_pasa(archivo_temporal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archivos.settings, "clamav_activo", True)
    monkeypatch.setattr(
        clamd, "ClamdNetworkSocket", lambda **kw: _ClienteFalso({str(archivo_temporal): ("OK", "")})
    )
    escanear_antivirus(archivo_temporal)  # no lanza nada


def test_archivo_infectado_se_rechaza(
    archivo_temporal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archivos.settings, "clamav_activo", True)
    monkeypatch.setattr(
        clamd,
        "ClamdNetworkSocket",
        lambda **kw: _ClienteFalso({str(archivo_temporal): ("FOUND", "Eicar-Test-Signature")}),
    )
    with pytest.raises(ArchivoRechazado) as exc:
        escanear_antivirus(archivo_temporal)
    assert exc.value.status_code == 415
    assert "Eicar-Test-Signature" in exc.value.detalle


def test_clamd_no_disponible_rechaza_la_subida(
    archivo_temporal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin clamd disponible la subida se RECHAZA: nunca se degrada a "sin escanear"."""
    monkeypatch.setattr(archivos.settings, "clamav_activo", True)
    monkeypatch.setattr(
        clamd,
        "ClamdNetworkSocket",
        lambda **kw: _ClienteFalso(lanza=clamd.ConnectionError("clamd no responde")),
    )
    with pytest.raises(ArchivoRechazado) as exc:
        escanear_antivirus(archivo_temporal)
    assert exc.value.status_code == 503
