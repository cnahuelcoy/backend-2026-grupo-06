"""Control persistente de intentos de inicio de sesión."""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as batch:
        batch.add_column(
            sa.Column(
                "intentos_fallidos", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.add_column(sa.Column("bloqueado_hasta", sa.DateTime(timezone=True)))


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_column("bloqueado_hasta")
        batch.drop_column("intentos_fallidos")
