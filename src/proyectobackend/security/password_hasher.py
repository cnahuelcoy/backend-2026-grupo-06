import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError


class PasswordHasher:
    def __init__(self):
        self._hasher = PasswordHash.recommended()
        self.hash_ficticio = self.hashear(secrets.token_urlsafe(24))

    def hashear(self, password: str) -> str:
        if not 12 <= len(password) <= 128:
            raise ValueError("La contraseña debe tener entre 12 y 128 caracteres")
        return self._hasher.hash(password)

    def verificar(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password, password_hash)
        except (PwdlibError, ValueError):
            return False
