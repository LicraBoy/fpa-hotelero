"""Entorno de Alembic: usa la misma URL y los mismos modelos que la aplicación.

La URL sale de `FPA_DATABASE_URL` (ver fpa/config.py). Las pruebas pueden pasar una conexión
ya abierta en `config.attributes["connection"]`.
"""

from alembic import context
from sqlalchemy import create_engine, pool

from fpa.config import settings
from fpa.modelos import Base

config = context.config
target_metadata = Base.metadata

# render_as_batch: SQLite no soporta ALTER TABLE completo; en otros motores no cambia nada.
_OPCIONES = {
    "target_metadata": target_metadata,
    "render_as_batch": True,
    "compare_type": True,
    "user_module_prefix": "fpa_tipos.",
}


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or settings.database_url
    context.configure(
        url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **_OPCIONES
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conexion = config.attributes.get("connection")
    if conexion is not None:
        context.configure(connection=conexion, **_OPCIONES)
        with context.begin_transaction():
            context.run_migrations()
        return

    url = config.get_main_option("sqlalchemy.url") or settings.database_url
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **_OPCIONES)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
