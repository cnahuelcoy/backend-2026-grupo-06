from dataclasses import dataclass, field
from datetime import datetime, timezone


def fecha_utc(fecha: datetime) -> datetime:
    if fecha.tzinfo is None:
        raise ValueError("La fecha debe incluir zona horaria")
    return fecha.astimezone(timezone.utc)


@dataclass(frozen=True)
class Sesion:
    id: str
    usuario_id: int
    familia_id: str
    refresh_hash: str = field(repr=False)
    version_tokens: int
    creada_en: datetime
    expira_en: datetime
    consumida_en: datetime | None = None
    revocada_en: datetime | None = None

    def vigente(self, ahora: datetime) -> bool:
        return (
            self.consumida_en is None
            and self.revocada_en is None
            and self.creada_en <= fecha_utc(ahora) < self.expira_en
        )
