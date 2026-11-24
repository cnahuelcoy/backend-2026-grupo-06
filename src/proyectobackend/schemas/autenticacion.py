from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from proyectobackend.domain.usuario import RolUsuario, normalizar_email
from proyectobackend.schemas.cliente import EMAIL_PATTERN


class IdentificadorUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_identificador(cls, valor):
        return normalizar_email(valor) if isinstance(valor, str) else valor


class UsuarioRegistro(IdentificadorUsuario):
    password: SecretStr = Field(min_length=12, max_length=128, exclude=True)


class UsuarioLogin(IdentificadorUsuario):
    password: SecretStr = Field(min_length=1, max_length=128, exclude=True)


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    rol: RolUsuario
    activo: bool
