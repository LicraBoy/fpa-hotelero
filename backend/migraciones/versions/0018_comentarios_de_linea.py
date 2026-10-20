"""comentarios por línea, sus revisiones y adjuntos

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-20 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comentario_linea",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("linea_id", sa.Integer(), nullable=False),
        sa.Column("linea_descripcion", sa.String(length=300), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("bloque", sa.String(length=4), nullable=False),
        sa.Column("padre_id", sa.Integer(), nullable=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("estatus", sa.String(length=12), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.ForeignKeyConstraint(["linea_id"], ["linea_reporte.id"]),
        sa.ForeignKeyConstraint(["padre_id"], ["comentario_linea.id"]),
        sa.ForeignKeyConstraint(["autor_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["responsable_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("comentario_linea", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_comentario_linea_hotel_id"), ["hotel_id"])
        batch_op.create_index(batch_op.f("ix_comentario_linea_padre_id"), ["padre_id"])
        batch_op.create_index("ix_comentario_hotel_periodo", ["hotel_id", "periodo"])

    op.create_table(
        "comentario_revision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comentario_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comentario_id"], ["comentario_linea.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("comentario_revision", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_comentario_revision_comentario_id"), ["comentario_id"])

    op.create_table(
        "adjunto_comentario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comentario_id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("extension", sa.String(length=8), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comentario_id"], ["comentario_linea.id"]),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("adjunto_comentario", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_adjunto_comentario_comentario_id"), ["comentario_id"])
        batch_op.create_index(batch_op.f("ix_adjunto_comentario_hotel_id"), ["hotel_id"])


def downgrade() -> None:
    with op.batch_alter_table("adjunto_comentario", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_adjunto_comentario_hotel_id"))
        batch_op.drop_index(batch_op.f("ix_adjunto_comentario_comentario_id"))
    op.drop_table("adjunto_comentario")
    with op.batch_alter_table("comentario_revision", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_comentario_revision_comentario_id"))
    op.drop_table("comentario_revision")
    with op.batch_alter_table("comentario_linea", schema=None) as batch_op:
        batch_op.drop_index("ix_comentario_hotel_periodo")
        batch_op.drop_index(batch_op.f("ix_comentario_linea_padre_id"))
        batch_op.drop_index(batch_op.f("ix_comentario_linea_hotel_id"))
    op.drop_table("comentario_linea")
