"""cierre de periodo del Variance y sus transiciones

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-20 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cierre_periodo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("estado", sa.String(length=12), nullable=False),
        sa.Column("version_mapeo_id", sa.Integer(), nullable=True),
        sa.Column("version_plan_id", sa.Integer(), nullable=True),
        sa.Column("version_estructura_id", sa.Integer(), nullable=True),
        sa.Column("congelado", sa.JSON(), nullable=True),
        sa.Column("huella_cifras", sa.String(length=64), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.ForeignKeyConstraint(["version_mapeo_id"], ["version_mapeo.id"]),
        sa.ForeignKeyConstraint(["version_plan_id"], ["version_plan.id"]),
        sa.ForeignKeyConstraint(["version_estructura_id"], ["version_estructura_reporte.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "periodo"),
    )
    with op.batch_alter_table("cierre_periodo", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cierre_periodo_hotel_id"), ["hotel_id"])

    op.create_table(
        "cierre_transicion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cierre_id", sa.Integer(), nullable=False),
        sa.Column("desde", sa.String(length=12), nullable=False),
        sa.Column("hacia", sa.String(length=12), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cierre_id"], ["cierre_periodo.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cierre_transicion", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cierre_transicion_cierre_id"), ["cierre_id"])


def downgrade() -> None:
    with op.batch_alter_table("cierre_transicion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cierre_transicion_cierre_id"))
    op.drop_table("cierre_transicion")
    with op.batch_alter_table("cierre_periodo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cierre_periodo_hotel_id"))
    op.drop_table("cierre_periodo")
