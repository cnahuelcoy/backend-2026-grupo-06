from datetime import datetime, timedelta, timezone
import re

import jwt

from proyectobackend.domain.usuario import Usuario
from proyectobackend.security.config import ConfiguracionJWT


class TokenInvalido(ValueError):
    pass


class JWTService:
    def __init__(self, configuracion: ConfiguracionJWT):
        self.configuracion = configuracion

    def emitir_access(self, usuario: Usuario) -> str:
        ahora = datetime.now(timezone.utc)
        return jwt.encode({
            "sub": str(usuario.id), "type": "access", "ver": usuario.version_tokens,
            "iat": ahora, "exp": ahora + timedelta(minutes=self.configuracion.minutos_access),
        }, self.configuracion.secret, algorithm="HS256")

    def validar_access(self, token: str) -> tuple[int, int]:
        try:
            claims = jwt.decode(
                token, self.configuracion.secret, algorithms=["HS256"],
                options={"require": ["sub", "exp", "iat", "type", "ver"]},
            )
            sub = claims["sub"]
            if not isinstance(sub, str) or re.fullmatch(r"[1-9][0-9]{0,9}", sub) is None:
                raise TokenInvalido()
            if int(sub) > 2147483647 or claims["type"] != "access":
                raise TokenInvalido()
            if type(claims["ver"]) is not int or claims["ver"] < 0:
                raise TokenInvalido()
            if type(claims["exp"]) is not int or type(claims["iat"]) is not int:
                raise TokenInvalido()
            if claims["exp"] <= claims["iat"]:
                raise TokenInvalido()
            return int(sub), claims["ver"]
        except (jwt.InvalidTokenError, ValueError, TypeError) as error:
            raise TokenInvalido("Token inválido o vencido") from error
