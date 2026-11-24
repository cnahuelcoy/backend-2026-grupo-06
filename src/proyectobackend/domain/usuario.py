from dataclasses import dataclass, field
from enum import StrEnum
import re


class RolUsuario(StrEnum):
    OPERADOR = "operador"
    ADMIN = "admin"


def normalizar_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 255 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
        raise ValueError("El identificador debe ser un correo válido")
    return email


@dataclass(frozen=True)
class Usuario:
    id: int
    email: str
    password_hash: str = field(repr=False)
    rol: RolUsuario = RolUsuario.OPERADOR
    activo: bool = True
    version_tokens: int = 0


class EmailUsuarioDuplicado(ValueError):
    pass


class UsuarioNoDisponible(ValueError):
    pass
