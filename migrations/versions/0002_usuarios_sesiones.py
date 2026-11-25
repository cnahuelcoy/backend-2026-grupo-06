"""Usuarios y persistencia de sesiones, separados de los clientes del taller."""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "rol",
            sa.Enum(
                "operador",
                "admin",
                name="rol_usuario",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
            server_default="operador",
        ),
        sa.Column(
            "activo", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("version_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("version_tokens >= 0", name="ck_usuario_version_tokens"),
        sa.CheckConstraint(
            "email = lower(trim(email))", name="ck_usuario_email_normalizado"
        ),
    )
    op.create_table(
        "sesiones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False
        ),
        sa.Column("familia_id", sa.String(36), nullable=False),
        sa.Column("refresh_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("version_tokens", sa.Integer(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumida_en", sa.DateTime(timezone=True)),
        sa.Column("revocada_en", sa.DateTime(timezone=True)),
        sa.CheckConstraint("expira_en > creada_en", name="ck_sesion_expiracion"),
        sa.CheckConstraint("length(refresh_hash) = 64", name="ck_sesion_hash_longitud"),
        sa.CheckConstraint("version_tokens >= 0", name="ck_sesion_version_tokens"),
    )
    op.create_index("ix_sesiones_usuario_id", "sesiones", ["usuario_id"])
    op.create_index("ix_sesiones_familia_id", "sesiones", ["familia_id"])


def downgrade() -> None:
    op.drop_index("ix_sesiones_familia_id", table_name="sesiones")
    op.drop_index("ix_sesiones_usuario_id", table_name="sesiones")
    op.drop_table("sesiones")
    op.drop_table("usuarios")
