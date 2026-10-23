"""calendario fiscal del Budget: ano_fiscal y periodo_fiscal

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ano_fiscal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("etiqueta", sa.String(length=9), nullable=False),
        sa.Column("mes_inicio", sa.Integer(), nullable=False),
        sa.Column("mes_fin", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=10), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "etiqueta"),
    )
    with op.batch_alter_table("ano_fiscal", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ano_fiscal_hotel_id"), ["hotel_id"])

    op.create_table(
        "periodo_fiscal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ano_fiscal_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("estado", sa.String(length=10), nullable=False),
        sa.Column("fecha_limite", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrado_por_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["ano_fiscal_id"], ["ano_fiscal.id"]),
        sa.ForeignKeyConstraint(["cerrado_por_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ano_fiscal_id", "periodo"),
    )
    with op.batch_alter_table("periodo_fiscal", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_periodo_fiscal_ano_fiscal_id"), ["ano_fiscal_id"])


def downgrade() -> None:
    with op.batch_alter_table("periodo_fiscal", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_periodo_fiscal_ano_fiscal_id"))
    op.drop_table("periodo_fiscal")
    with op.batch_alter_table("ano_fiscal", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ano_fiscal_hotel_id"))
    op.drop_table("ano_fiscal")
