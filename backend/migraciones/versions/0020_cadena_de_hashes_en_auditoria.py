"""cadena de hashes en la bitácora de auditoría

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-20 21:00:00.000000

Los eventos que ya existían se sellan en esta migración, en orden de id y por organización: desde
aquí en adelante se puede demostrar que no cambiaron, pero no antes (nada prueba lo anterior).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)
from fpa.servicios.cadena_auditoria import GENESIS, calcular_hash

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_eventos = sa.table(
    "evento_auditoria",
    sa.column("id", sa.Integer),
    sa.column("organizacion_id", sa.Integer),
    sa.column("hotel_id", sa.Integer),
    sa.column("usuario_id", sa.Integer),
    sa.column("accion", sa.String),
    sa.column("entidad", sa.String),
    sa.column("entidad_id", sa.Integer),
    sa.column("detalle", sa.JSON),
    sa.column("creado_en", sa.DateTime(timezone=True)),
    sa.column("hash_previo", sa.String),
    sa.column("hash", sa.String),
)


def upgrade() -> None:
    with op.batch_alter_table("evento_auditoria", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("hash_previo", sa.String(length=64), server_default="", nullable=False)
        )
        batch_op.add_column(
            sa.Column("hash", sa.String(length=64), server_default="", nullable=False)
        )

    conexion = op.get_bind()
    previos: dict[int, str] = {}
    filas = conexion.execute(sa.select(_eventos).order_by(_eventos.c.id)).mappings().all()
    for fila in filas:
        previo = previos.get(fila["organizacion_id"], GENESIS)
        sello = calcular_hash(
            hash_previo=previo,
            organizacion_id=fila["organizacion_id"],
            hotel_id=fila["hotel_id"],
            usuario_id=fila["usuario_id"],
            accion=fila["accion"],
            entidad=fila["entidad"],
            entidad_id=fila["entidad_id"],
            detalle=fila["detalle"],
            creado_en=fila["creado_en"],
        )
        conexion.execute(
            sa.update(_eventos)
            .where(_eventos.c.id == fila["id"])
            .values(hash_previo=previo, hash=sello)
        )
        previos[fila["organizacion_id"]] = sello


def downgrade() -> None:
    with op.batch_alter_table("evento_auditoria", schema=None) as batch_op:
        batch_op.drop_column("hash")
        batch_op.drop_column("hash_previo")
