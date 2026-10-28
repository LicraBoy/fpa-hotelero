"""bloque inferior de la hoja de una seccion del Budget: hoja_seccion_mes

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-27 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hoja_seccion_mes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ciclo_id", sa.Integer(), nullable=False),
        sa.Column("seccion_linea_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("inflacion", fpa_tipos.Medida(), nullable=True),
        sa.Column("est_act_total", fpa_tipos.Medida(), nullable=True),
        sa.Column("budget_previo_total", fpa_tipos.Medida(), nullable=True),
        sa.Column("origen", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["ciclo_id"], ["ciclo_presupuesto.id"]),
        sa.ForeignKeyConstraint(["seccion_linea_id"], ["linea_reporte.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ciclo_id", "seccion_linea_id", "periodo"),
    )
    with op.batch_alter_table("hoja_seccion_mes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_hoja_seccion_mes_ciclo_id"), ["ciclo_id"])


def downgrade() -> None:
    with op.batch_alter_table("hoja_seccion_mes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_hoja_seccion_mes_ciclo_id"))
    op.drop_table("hoja_seccion_mes")
