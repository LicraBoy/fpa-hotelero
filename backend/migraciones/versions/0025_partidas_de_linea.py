"""partidas de una cuenta del Budget: partida, partida_mes, inflacion y referencia por linea

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-28 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("linea_presupuesto_captura", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("usa_partidas", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.create_table(
        "linea_presupuesto_partida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linea_captura_id", sa.Integer(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("concepto", sa.String(length=120), nullable=False),
        sa.Column("cantidad", fpa_tipos.Medida(), nullable=False),
        sa.Column("unidad", sa.String(length=20), nullable=True),
        sa.Column("costo", fpa_tipos.Medida(), nullable=False),
        sa.Column("metodo", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["linea_captura_id"], ["linea_presupuesto_captura.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("linea_presupuesto_partida", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_partida_linea_captura_id"), ["linea_captura_id"]
        )
    op.create_table(
        "linea_presupuesto_partida_mes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partida_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("importe", fpa_tipos.Medida(), nullable=False),
        sa.ForeignKeyConstraint(["partida_id"], ["linea_presupuesto_partida.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partida_id", "periodo"),
    )
    with op.batch_alter_table("linea_presupuesto_partida_mes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_partida_mes_partida_id"), ["partida_id"]
        )
    op.create_table(
        "linea_presupuesto_inflacion_mes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linea_captura_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("tasa", fpa_tipos.Medida(), nullable=False),
        sa.ForeignKeyConstraint(["linea_captura_id"], ["linea_presupuesto_captura.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("linea_captura_id", "periodo"),
    )
    with op.batch_alter_table("linea_presupuesto_inflacion_mes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_inflacion_mes_linea_captura_id"), ["linea_captura_id"]
        )
    op.create_table(
        "linea_presupuesto_referencia_mes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linea_captura_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("est_act", fpa_tipos.Medida(), nullable=True),
        sa.Column("budget_previo", fpa_tipos.Medida(), nullable=True),
        sa.Column("origen", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["linea_captura_id"], ["linea_presupuesto_captura.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("linea_captura_id", "periodo"),
    )
    with op.batch_alter_table("linea_presupuesto_referencia_mes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_referencia_mes_linea_captura_id"),
            ["linea_captura_id"],
        )


def downgrade() -> None:
    for tabla, indice in (
        ("linea_presupuesto_referencia_mes", "ix_linea_presupuesto_referencia_mes_linea_captura_id"),
        ("linea_presupuesto_inflacion_mes", "ix_linea_presupuesto_inflacion_mes_linea_captura_id"),
        ("linea_presupuesto_partida_mes", "ix_linea_presupuesto_partida_mes_partida_id"),
        ("linea_presupuesto_partida", "ix_linea_presupuesto_partida_linea_captura_id"),
    ):
        with op.batch_alter_table(tabla, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(indice))
        op.drop_table(tabla)
    with op.batch_alter_table("linea_presupuesto_captura", schema=None) as batch_op:
        batch_op.drop_column("usa_partidas")
