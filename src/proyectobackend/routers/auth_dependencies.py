from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from proyectobackend.domain.usuario import RolUsuario, Usuario
from proyectobackend.repositories.usuario_repository import UsuarioRepository
from proyectobackend.security.config import ConfiguracionJWT
from proyectobackend.security.jwt_service import JWTService, TokenInvalido
from proyectobackend.security.password_hasher import PasswordHasher
from proyectobackend.services.auth_service import AuthService


bearer = HTTPBearer(auto_error=False)


def error_acceso():
    return HTTPException(
        status_code=401,
        detail={
            "code": "INVALID_ACCESS_TOKEN",
            "message": "Acceso bloqueado",
            "details": [],
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache
def get_jwt_service() -> JWTService:
    return JWTService(ConfiguracionJWT.desde_entorno())


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return PasswordHasher()


def get_usuario_repository() -> UsuarioRepository:
    return UsuarioRepository()


def get_auth_service(
    usuarios: UsuarioRepository = Depends(get_usuario_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    tokens: JWTService = Depends(get_jwt_service),
) -> AuthService:
    return AuthService(usuarios, hasher, tokens)


def get_usuario_actual(
    credencial: HTTPAuthorizationCredentials | None = Depends(bearer),
    tokens: JWTService = Depends(get_jwt_service),
    usuarios: UsuarioRepository = Depends(get_usuario_repository),
) -> Usuario:
    if credencial is None:
        raise error_acceso()
    try:
        usuario_id, version = tokens.validar_access(credencial.credentials)
    except TokenInvalido:
        raise error_acceso() from None
    usuario = usuarios.buscar_por_id(usuario_id)
    if usuario is None or not usuario.activo or usuario.version_tokens != version:
        raise error_acceso()
    return usuario


def autorizar_negocio(
    request: Request, usuario: Usuario = Depends(get_usuario_actual)
) -> None:
    if request.method == "DELETE" and usuario.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Acceso bloqueado",
                "details": [],
            },
        )
