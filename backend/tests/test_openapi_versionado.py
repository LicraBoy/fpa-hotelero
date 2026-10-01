"""El OpenAPI versionado del frontend coincide con el de la API (sin deriva entre ambos)."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
VERSIONADO = RAIZ / "frontend" / "src" / "api" / "openapi.json"
sys.path.insert(0, str(RAIZ / "backend" / "scripts"))

from exportar_openapi import openapi_texto  # noqa: E402


def test_el_openapi_versionado_esta_al_dia() -> None:
    assert VERSIONADO.exists(), "Falta frontend/src/api/openapi.json: corre `npm run api:tipos`"
    actual = openapi_texto()
    versionado = VERSIONADO.read_text(encoding="utf-8")
    assert versionado.replace("\r\n", "\n") == actual, (
        "La API cambió y los tipos del frontend no: corre `npm run api:tipos` en frontend/ "
        "y commitea src/api/openapi.json y src/api/schema.d.ts"
    )


def test_el_openapi_es_determinista() -> None:
    assert openapi_texto() == openapi_texto()
