"""consumo mensual de una cuenta del Budget (Diesel, Gas, Electricity, Water)

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-29 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("linea_presupuesto_captura", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("usa_consumo", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("unidad_consumo", sa.String(length=10), nullable=True))
    op.create_table(
        "linea_presupuesto_consumo_mes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linea_captura_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("bloque", sa.String(length=12), nullable=False),
        sa.Column("unidades", fpa_tipos.Medida(), nullable=True),
        sa.Column("costo_unitario", fpa_tipos.Medida(), nullable=True),
        sa.Column("total", fpa_tipos.Medida(), nullable=True),
        sa.ForeignKeyConstraint(["linea_captura_id"], ["linea_presupuesto_captura.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("linea_captura_id", "periodo", "bloque"),
    )
    with op.batch_alter_table("linea_presupuesto_consumo_mes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_consumo_mes_linea_captura_id"), ["linea_captura_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("linea_presupuesto_consumo_mes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_linea_presupuesto_consumo_mes_linea_captura_id"))
    op.drop_table("linea_presupuesto_consumo_mes")
    with op.batch_alter_table("linea_presupuesto_captura", schema=None) as batch_op:
        batch_op.drop_column("unidad_consumo")
        batch_op.drop_column("usa_consumo")
