from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from proyectobackend.database.session import SessionLocal
from proyectobackend.domain.usuario import (
    EmailUsuarioDuplicado, RolUsuario, Usuario, normalizar_email,
)
from proyectobackend.models.sesion import SesionModel
from proyectobackend.models.usuario import UsuarioModel


class UsuarioRepository:
    def __init__(self, sesiones=None):
        self.sesiones = sesiones if sesiones is not None else SessionLocal

    @staticmethod
    def _to_domain(model: UsuarioModel) -> Usuario:
        return Usuario(
            id=model.id, email=model.email, password_hash=model.password_hash,
            rol=model.rol, activo=model.activo, version_tokens=model.version_tokens,
        )

    def crear(self, email: str, password_hash: str, rol: RolUsuario = RolUsuario.OPERADOR) -> Usuario:
        email = normalizar_email(email)
        try:
            with self.sesiones.begin() as session:
                model = UsuarioModel(email=email, password_hash=password_hash, rol=rol)
                session.add(model)
                session.flush()
                usuario = self._to_domain(model)
            return usuario
        except IntegrityError as error:
            if self.buscar_por_email(email) is not None:
                raise EmailUsuarioDuplicado("El identificador ya está registrado") from error
            raise

    def buscar_por_id(self, usuario_id: int) -> Usuario | None:
        with self.sesiones() as session:
            model = session.get(UsuarioModel, usuario_id)
            return self._to_domain(model) if model else None

    def buscar_por_email(self, email: str) -> Usuario | None:
        with self.sesiones() as session:
            model = session.scalar(select(UsuarioModel).where(
                UsuarioModel.email == normalizar_email(email),
            ))
            return self._to_domain(model) if model else None

    def _invalidar(self, usuario_id: int, cambios: dict) -> Usuario | None:
        with self.sesiones.begin() as session:
            model = session.scalar(
                update(UsuarioModel).where(UsuarioModel.id == usuario_id)
                .values(**cambios, version_tokens=UsuarioModel.version_tokens + 1)
                .returning(UsuarioModel)
            )
            if model is None:
                return None
            session.execute(
                update(SesionModel).where(
                    SesionModel.usuario_id == usuario_id,
                    SesionModel.revocada_en.is_(None),
                ).values(revocada_en=datetime.now(timezone.utc))
            )
            usuario = self._to_domain(model)
        return usuario

    def invalidar_sesiones(self, usuario_id: int) -> Usuario | None:
        return self._invalidar(usuario_id, {})

    def cambiar_password_hash(self, usuario_id: int, password_hash: str) -> Usuario | None:
        return self._invalidar(usuario_id, {"password_hash": password_hash})

    def desactivar(self, usuario_id: int) -> Usuario | None:
        return self._invalidar(usuario_id, {"activo": False})
