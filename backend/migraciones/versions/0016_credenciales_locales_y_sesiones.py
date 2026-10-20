"""credenciales locales y sesiones

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("password_cambiada_en", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "debe_cambiar_password", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        )
        batch_op.add_column(sa.Column("totp_secreto", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("totp_activo", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("intentos_fallidos", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "sesion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultimo_uso", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agente", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("sesion", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sesion_usuario_id"), ["usuario_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("sesion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sesion_usuario_id"))
    op.drop_table("sesion")
    with op.batch_alter_table("usuario", schema=None) as batch_op:
        batch_op.drop_column("bloqueado_hasta")
        batch_op.drop_column("intentos_fallidos")
        batch_op.drop_column("totp_activo")
        batch_op.drop_column("totp_secreto")
        batch_op.drop_column("debe_cambiar_password")
        batch_op.drop_column("password_cambiada_en")
        batch_op.drop_column("password_hash")
