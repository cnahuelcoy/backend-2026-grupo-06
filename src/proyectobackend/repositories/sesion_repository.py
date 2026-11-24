from datetime import datetime, timezone
import re
from uuid import uuid4

from sqlalchemy import select, update

from proyectobackend.database.session import SessionLocal
from proyectobackend.domain.sesion import Sesion, fecha_utc
from proyectobackend.domain.usuario import UsuarioNoDisponible
from proyectobackend.models.sesion import SesionModel
from proyectobackend.models.usuario import UsuarioModel


class SesionRepository:
    def __init__(self, sesiones=None):
        self.sesiones = sesiones if sesiones is not None else SessionLocal

    @staticmethod
    def _to_domain(model: SesionModel) -> Sesion:
        def utc(fecha):
            return fecha.replace(tzinfo=timezone.utc) if fecha is not None and fecha.tzinfo is None else fecha

        return Sesion(
            id=model.id, usuario_id=model.usuario_id, familia_id=model.familia_id,
            refresh_hash=model.refresh_hash, version_tokens=model.version_tokens,
            creada_en=utc(model.creada_en), expira_en=utc(model.expira_en),
            consumida_en=utc(model.consumida_en), revocada_en=utc(model.revocada_en),
        )

    def crear(self, usuario_id: int, refresh_hash: str, expira_en: datetime,
              version_tokens: int) -> Sesion:
        if re.fullmatch(r"[0-9a-f]{64}", refresh_hash) is None:
            raise ValueError("Se requiere el hash hexadecimal del refresh, no el token")
        ahora = datetime.now(timezone.utc)
        expira_en = fecha_utc(expira_en)
        if expira_en <= ahora:
            raise ValueError("La sesión debe expirar en el futuro")
        with self.sesiones.begin() as session:
            usuario = session.scalar(select(UsuarioModel).where(
                UsuarioModel.id == usuario_id,
            ).with_for_update())
            if usuario is None or not usuario.activo or usuario.version_tokens != version_tokens:
                raise UsuarioNoDisponible("Usuario inactivo, inexistente o versión de sesión vencida")
            model = SesionModel(
                id=str(uuid4()), usuario_id=usuario_id, familia_id=str(uuid4()),
                refresh_hash=refresh_hash, version_tokens=version_tokens,
                creada_en=ahora, expira_en=expira_en,
            )
            session.add(model)
            session.flush()
            sesion = self._to_domain(model)
        return sesion

    def buscar_por_hash(self, refresh_hash: str) -> Sesion | None:
        with self.sesiones() as session:
            model = session.scalar(select(SesionModel).where(SesionModel.refresh_hash == refresh_hash))
            return self._to_domain(model) if model else None

    def consumir(self, sesion_id: str, ahora: datetime) -> bool:
        ahora = fecha_utc(ahora)
        with self.sesiones.begin() as session:
            resultado = session.execute(update(SesionModel).where(
                SesionModel.id == sesion_id,
                SesionModel.creada_en <= ahora,
                SesionModel.expira_en > ahora,
                SesionModel.consumida_en.is_(None),
                SesionModel.revocada_en.is_(None),
            ).values(consumida_en=ahora))
            return resultado.rowcount == 1

    def revocar_familia(self, familia_id: str) -> int:
        with self.sesiones.begin() as session:
            resultado = session.execute(update(SesionModel).where(
                SesionModel.familia_id == familia_id,
                SesionModel.revocada_en.is_(None),
            ).values(revocada_en=datetime.now(timezone.utc)))
            return resultado.rowcount
