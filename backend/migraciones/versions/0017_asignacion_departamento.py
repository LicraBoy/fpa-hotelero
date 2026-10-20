"""secciones del Variance asignadas a responsables de departamento

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-20 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asignacion_departamento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("seccion", sa.String(length=300), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "hotel_id", "seccion"),
    )
    with op.batch_alter_table("asignacion_departamento", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_asignacion_departamento_hotel_id"), ["hotel_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_asignacion_departamento_usuario_id"), ["usuario_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("asignacion_departamento", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_asignacion_departamento_usuario_id"))
        batch_op.drop_index(batch_op.f("ix_asignacion_departamento_hotel_id"))
    op.drop_table("asignacion_departamento")
