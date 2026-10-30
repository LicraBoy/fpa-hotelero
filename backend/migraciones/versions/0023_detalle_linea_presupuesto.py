"""detalle por cuenta de una linea del Budget: linea_presupuesto_detalle y linea_plan_detalle

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "linea_presupuesto_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linea_captura_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("metodo", sa.String(length=6), nullable=False),
        sa.Column("base", fpa_tipos.Medida(), nullable=True),
        sa.Column("factor", fpa_tipos.Medida(), nullable=True),
        sa.Column("monto_fijo", fpa_tipos.Medida(), nullable=True),
        sa.Column("importe", fpa_tipos.Medida(), nullable=False),
        sa.ForeignKeyConstraint(["linea_captura_id"], ["linea_presupuesto_captura.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("linea_captura_id", "periodo"),
    )
    with op.batch_alter_table("linea_presupuesto_detalle", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_detalle_linea_captura_id"), ["linea_captura_id"]
        )

    op.create_table(
        "linea_plan_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_plan_id", sa.Integer(), nullable=False),
        sa.Column("linea_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("metodo", sa.String(length=6), nullable=False),
        sa.Column("base", fpa_tipos.Medida(), nullable=True),
        sa.Column("factor", fpa_tipos.Medida(), nullable=True),
        sa.Column("monto_fijo", fpa_tipos.Medida(), nullable=True),
        sa.Column("importe", fpa_tipos.Medida(), nullable=False),
        sa.ForeignKeyConstraint(["version_plan_id"], ["version_plan.id"]),
        sa.ForeignKeyConstraint(["linea_id"], ["linea_reporte.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_plan_id", "linea_id", "periodo"),
    )
    with op.batch_alter_table("linea_plan_detalle", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_plan_detalle_version_plan_id"), ["version_plan_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("linea_plan_detalle", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_linea_plan_detalle_version_plan_id"))
    op.drop_table("linea_plan_detalle")

    with op.batch_alter_table("linea_presupuesto_detalle", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_linea_presupuesto_detalle_linea_captura_id"))
    op.drop_table("linea_presupuesto_detalle")
