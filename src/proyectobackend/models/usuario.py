from sqlalchemy import Boolean, CheckConstraint, Enum, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from proyectobackend.database.base import Base
from proyectobackend.domain.usuario import RolUsuario


class UsuarioModel(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("version_tokens >= 0", name="ck_usuario_version_tokens"),
        CheckConstraint("email = lower(trim(email))", name="ck_usuario_email_normalizado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        Enum(
            RolUsuario, values_callable=lambda roles: [rol.value for rol in roles],
            name="rol_usuario", native_enum=False, create_constraint=True,
        ),
        nullable=False, default=RolUsuario.OPERADOR, server_default="operador",
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    version_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
