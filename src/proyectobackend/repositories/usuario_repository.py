from datetime import datetime, timedelta, timezone

from sqlalchemy import case, or_, select, update
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
            intentos_fallidos=model.intentos_fallidos,
            bloqueado_hasta=(model.bloqueado_hasta.replace(tzinfo=timezone.utc)
                            if model.bloqueado_hasta is not None and model.bloqueado_hasta.tzinfo is None
                            else model.bloqueado_hasta),
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

    def _invalidar(self, usuario_id: int, cambios: dict, esperado: Usuario | None = None) -> Usuario | None:
        with self.sesiones.begin() as session:
            sentencia = update(UsuarioModel).where(UsuarioModel.id == usuario_id)
            if esperado is not None:
                sentencia = sentencia.where(
                    UsuarioModel.version_tokens == esperado.version_tokens,
                    UsuarioModel.password_hash == esperado.password_hash,
                )
            model = session.scalar(
                sentencia
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
        return self._invalidar(usuario_id, {
            "password_hash": password_hash, "intentos_fallidos": 0, "bloqueado_hasta": None,
        })

    def desactivar(self, usuario_id: int) -> Usuario | None:
        return self._invalidar(usuario_id, {"activo": False})

    def sincronizar_admin(self, esperado: Usuario, password_hash: str) -> Usuario | None:
        return self._invalidar(esperado.id, {
            "password_hash": password_hash, "rol": RolUsuario.ADMIN, "activo": True,
            "intentos_fallidos": 0, "bloqueado_hasta": None,
        }, esperado=esperado)

    def registrar_login(self, usuario_id: int, valida: bool, version_esperada: int,
                        ahora: datetime) -> Usuario | None:
        with self.sesiones.begin() as session:
            sentencia = update(UsuarioModel).where(
                UsuarioModel.id == usuario_id, UsuarioModel.activo.is_(True),
                UsuarioModel.version_tokens == version_esperada,
                or_(UsuarioModel.bloqueado_hasta.is_(None), UsuarioModel.bloqueado_hasta <= ahora),
            )
            if valida:
                model = session.scalar(sentencia.values(
                    intentos_fallidos=0, bloqueado_hasta=None,
                ).returning(UsuarioModel))
                return self._to_domain(model) if model else None
            intentos = UsuarioModel.intentos_fallidos + 1
            session.execute(sentencia.values(
                intentos_fallidos=case((intentos >= 5, 0), else_=intentos),
                bloqueado_hasta=case((intentos >= 5, ahora + timedelta(minutes=15)), else_=None),
            ))
            return None
