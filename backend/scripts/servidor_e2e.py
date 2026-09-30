"""Levanta un backend LIMPIO para las pruebas de navegador (Playwright).

Usa una base de datos y un almacenamiento temporales (se borran al iniciar), aplica las
migraciones, siembra los usuarios de desarrollo y arranca la API en el puerto 8101.
Nunca toca la base de datos de desarrollo normal.

Uso (desde backend/):  .venv\\Scripts\\python scripts/servidor_e2e.py
"""

import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TEMPORAL = RAIZ / ".e2e"
PUERTO = int(os.environ.get("FPA_E2E_PUERTO", "8101"))

shutil.rmtree(TEMPORAL, ignore_errors=True)
TEMPORAL.mkdir()

# Antes de importar la aplicación: la configuración se lee al importar.
os.environ["FPA_DATABASE_URL"] = f"sqlite:///{(TEMPORAL / 'e2e.db').as_posix()}"
os.environ["FPA_STORAGE_DIR"] = str(TEMPORAL / "storage")
os.environ["FPA_ENTORNO"] = "desarrollo"
os.environ["FPA_CORS_ORIGINS"] = '["http://localhost:5181","http://127.0.0.1:5181"]'
sys.path.insert(0, str(RAIZ))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

command.upgrade(Config(str(RAIZ / "alembic.ini")), "head")

from fpa.db import SessionLocal  # noqa: E402
from fpa.semilla import sembrar_torres  # noqa: E402

with SessionLocal() as db:
    sembrar_torres(db)
    db.commit()

import uvicorn  # noqa: E402

uvicorn.run("fpa.main:app", host="127.0.0.1", port=PUERTO, log_level="warning")
