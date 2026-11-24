from datetime import datetime, timezone

from proyectobackend.domain.usuario import EmailUsuarioDuplicado, RolUsuario
from proyectobackend.repositories.usuario_repository import UsuarioRepository
from proyectobackend.schemas.autenticacion import UsuarioLogin, UsuarioRegistro
from proyectobackend.security.jwt_service import JWTService
from proyectobackend.security.password_hasher import PasswordHasher


class CredencialesInvalidas(ValueError):
    pass


class AuthService:
    def __init__(self, usuarios: UsuarioRepository, hasher: PasswordHasher, tokens: JWTService):
        self.usuarios = usuarios
        self.hasher = hasher
        self.tokens = tokens

    def registrar(self, datos: UsuarioRegistro):
        return self.usuarios.crear(
            datos.email, self.hasher.hashear(datos.password.get_secret_value()), RolUsuario.OPERADOR,
        )

    def asegurar_admin(self, email: str, password: str):
        try:
            datos = UsuarioRegistro(email=email, password=password)
        except ValueError:
            raise ValueError("Configura ADMIN_EMAIL y ADMIN_PASSWORD (12 a 128 caracteres)") from None
        for _ in range(3):
            usuario = self.usuarios.buscar_por_email(datos.email)
            if usuario is None:
                try:
                    return self.usuarios.crear(datos.email, self.hasher.hashear(password), RolUsuario.ADMIN)
                except EmailUsuarioDuplicado:
                    continue
            misma_password = self.hasher.verificar(password, usuario.password_hash)
            if misma_password and usuario.activo and usuario.rol == RolUsuario.ADMIN:
                return usuario
            hash_nuevo = usuario.password_hash if misma_password else self.hasher.hashear(password)
            actualizado = self.usuarios.sincronizar_admin(usuario, hash_nuevo)
            if actualizado is not None:
                return actualizado
        raise RuntimeError("No se pudo sincronizar el administrador; reintenta el arranque")

    def login(self, datos: UsuarioLogin) -> str:
        usuario = self.usuarios.buscar_por_email(datos.email)
        hash_esperado = usuario.password_hash if usuario else self.hasher.hash_ficticio
        valida = self.hasher.verificar(datos.password.get_secret_value(), hash_esperado)
        if usuario is None:
            raise CredencialesInvalidas()
        actualizado = self.usuarios.registrar_login(
            usuario.id, valida, usuario.version_tokens, datetime.now(timezone.utc),
        )
        if actualizado is None:
            raise CredencialesInvalidas()
        return self.tokens.emitir_access(actualizado)
