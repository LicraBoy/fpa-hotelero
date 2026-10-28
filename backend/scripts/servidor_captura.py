"""Levanta un backend sobre una COPIA de la base de desarrollo, para tomar capturas con datos reales.

Copia `fpa_dev.db` a `.captura/captura.db` (la base real no se toca), aplica las migraciones y
arranca la API en el puerto 8102. Es solo para las capturas de `frontend/capturas/`.

Uso (desde backend/):  .venv\\Scripts\\python scripts/servidor_captura.py
"""

import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TEMPORAL = RAIZ / ".captura"
PUERTO = int(os.environ.get("FPA_CAPTURA_PUERTO", "8102"))
WEB = os.environ.get("FPA_CAPTURA_WEB", "5182")

fuente = RAIZ / "fpa_dev.db"
if not fuente.exists():
    sys.exit("No existe fpa_dev.db: no hay datos reales con los que capturar.")

shutil.rmtree(TEMPORAL, ignore_errors=True)
TEMPORAL.mkdir()
shutil.copy2(fuente, TEMPORAL / "captura.db")

# Antes de importar la aplicación: la configuración se lee al importar.
os.environ["FPA_DATABASE_URL"] = f"sqlite:///{(TEMPORAL / 'captura.db').as_posix()}"
os.environ["FPA_STORAGE_DIR"] = str(TEMPORAL / "storage")
os.environ["FPA_ENTORNO"] = "desarrollo"
os.environ["FPA_CORS_ORIGINS"] = f'["http://localhost:{WEB}","http://127.0.0.1:{WEB}"]'
sys.path.insert(0, str(RAIZ))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

command.upgrade(Config(str(RAIZ / "alembic.ini")), "head")

import uvicorn  # noqa: E402

uvicorn.run("fpa.main:app", host="127.0.0.1", port=PUERTO, log_level="warning")
