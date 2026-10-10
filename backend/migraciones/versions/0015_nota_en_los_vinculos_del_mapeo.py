"""nota en los vinculos del mapeo

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-09 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from fpa.modelos import tipos as fpa_tipos  # noqa: F401  (tipos propios, p. ej. Dinero)

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mapeo_linea_cuenta", schema=None) as batch_op:
        batch_op.add_column(sa.Column("nota", sa.String(length=160), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("mapeo_linea_cuenta", schema=None) as batch_op:
        batch_op.drop_column("nota")
