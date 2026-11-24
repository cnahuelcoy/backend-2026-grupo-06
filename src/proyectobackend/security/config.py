from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class ConfiguracionJWT:
    secret: str = field(repr=False)
    minutos_access: int = 15

    def __post_init__(self):
        if len(self.secret.encode("utf-8")) < 32 or self.secret.startswith("CAMBIAR_"):
            raise ValueError("Configura JWT_SECRET_KEY con un secreto aleatorio de al menos 32 bytes")
        if not 1 <= self.minutos_access <= 30:
            raise ValueError("JWT_ACCESS_MINUTES debe estar entre 1 y 30")

    @classmethod
    def desde_entorno(cls):
        return cls(
            secret=os.getenv("JWT_SECRET_KEY", ""),
            minutos_access=int(os.getenv("JWT_ACCESS_MINUTES", "15")),
        )
