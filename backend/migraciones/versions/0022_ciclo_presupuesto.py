"""ciclo de captura del Budget: ciclo_presupuesto y sus lineas (Fase 7.1)

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-22 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ciclo_presupuesto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("ano_fiscal_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=12), nullable=False),
        sa.Column("version_estructura_id", sa.Integer(), nullable=True),
        sa.Column("creado_por_id", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aprobado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_plan_resultante_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.ForeignKeyConstraint(["ano_fiscal_id"], ["ano_fiscal.id"]),
        sa.ForeignKeyConstraint(["version_estructura_id"], ["version_estructura_reporte.id"]),
        sa.ForeignKeyConstraint(["creado_por_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["version_plan_resultante_id"], ["version_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "ano_fiscal_id", "numero"),
    )
    with op.batch_alter_table("ciclo_presupuesto", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ciclo_presupuesto_hotel_id"), ["hotel_id"])
        batch_op.create_index(batch_op.f("ix_ciclo_presupuesto_ano_fiscal_id"), ["ano_fiscal_id"])

    op.create_table(
        "ciclo_transicion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ciclo_id", sa.Integer(), nullable=False),
        sa.Column("desde", sa.String(length=12), nullable=False),
        sa.Column("hacia", sa.String(length=12), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ciclo_id"], ["ciclo_presupuesto.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ciclo_transicion", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ciclo_transicion_ciclo_id"), ["ciclo_id"])

    op.create_table(
        "perfil_distribucion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=True),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("pesos", sa.JSON(), nullable=False),
        sa.Column("es_sistema", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("perfil_distribucion", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_perfil_distribucion_hotel_id"), ["hotel_id"])

    op.create_table(
        "linea_presupuesto_captura",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ciclo_id", sa.Integer(), nullable=False),
        sa.Column("linea_id", sa.Integer(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("objetivo", fpa_tipos.Medida(), nullable=True),
        sa.Column("propuesta_anual", fpa_tipos.Medida(), nullable=True),
        sa.Column("perfil_distribucion_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=12), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ciclo_id"], ["ciclo_presupuesto.id"]),
        sa.ForeignKeyConstraint(["linea_id"], ["linea_reporte.id"]),
        sa.ForeignKeyConstraint(["responsable_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["perfil_distribucion_id"], ["perfil_distribucion.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ciclo_id", "linea_id"),
    )
    with op.batch_alter_table("linea_presupuesto_captura", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_linea_presupuesto_captura_ciclo_id"), ["ciclo_id"])

    op.create_table(
        "linea_presupuesto_mensual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("linea_captura_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=7), nullable=False),
        sa.Column("importe", fpa_tipos.Medida(), nullable=False),
        sa.ForeignKeyConstraint(["linea_captura_id"], ["linea_presupuesto_captura.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("linea_captura_id", "periodo"),
    )
    with op.batch_alter_table("linea_presupuesto_mensual", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_linea_presupuesto_mensual_linea_captura_id"), ["linea_captura_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("linea_presupuesto_mensual", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_linea_presupuesto_mensual_linea_captura_id"))
    op.drop_table("linea_presupuesto_mensual")

    with op.batch_alter_table("linea_presupuesto_captura", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_linea_presupuesto_captura_ciclo_id"))
    op.drop_table("linea_presupuesto_captura")

    with op.batch_alter_table("perfil_distribucion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_perfil_distribucion_hotel_id"))
    op.drop_table("perfil_distribucion")

    with op.batch_alter_table("ciclo_transicion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ciclo_transicion_ciclo_id"))
    op.drop_table("ciclo_transicion")

    with op.batch_alter_table("ciclo_presupuesto", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ciclo_presupuesto_ano_fiscal_id"))
        batch_op.drop_index(batch_op.f("ix_ciclo_presupuesto_hotel_id"))
    op.drop_table("ciclo_presupuesto")
