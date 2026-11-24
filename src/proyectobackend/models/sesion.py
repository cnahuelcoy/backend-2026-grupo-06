from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from proyectobackend.database.base import Base


class SesionModel(Base):
    __tablename__ = "sesiones"
    __table_args__ = (
        CheckConstraint("expira_en > creada_en", name="ck_sesion_expiracion"),
        CheckConstraint("length(refresh_hash) = 64", name="ck_sesion_hash_longitud"),
        CheckConstraint("version_tokens >= 0", name="ck_sesion_version_tokens"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    familia_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    version_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
