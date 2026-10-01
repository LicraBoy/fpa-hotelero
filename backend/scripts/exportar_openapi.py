"""Escribe el OpenAPI de la API en un archivo JSON (determinístico).

De ese archivo salen los tipos de TypeScript del frontend (`npm run api:tipos`). Una prueba del
backend verifica que el archivo versionado coincide con el OpenAPI actual: si cambias una ruta o un
esquema y no regeneras, falla.

Uso (desde backend/):  python scripts/exportar_openapi.py ../frontend/src/api/openapi.json
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from fpa.main import app  # noqa: E402


def openapi_texto() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if destino is None:
        sys.stdout.write(openapi_texto())
    else:
        destino.write_text(openapi_texto(), encoding="utf-8", newline="\n")
