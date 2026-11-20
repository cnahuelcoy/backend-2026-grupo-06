from dataclasses import dataclass
from datetime import date
from enum import Enum


class ConflictoOrdenTrabajo(ValueError):
    """La orden cambió después de la lectura usada para validar el PATCH."""

    def __init__(self):
        super().__init__(
            "WORK_ORDER_CONCURRENT_UPDATE:La orden fue modificada por otra "
            "solicitud. Vuelve a consultarla antes de intentar actualizarla."
        )


class EstadoOrdenTrabajo(str, Enum):
    PENDIENTE = "pendiente"
    EN_REPARACION = "en_reparacion"
    FINALIZADA = "finalizada"


@dataclass
class OrdenTrabajo:
    vehiculo_id: int
    fecha_ingreso: date
    descripcion_problema: str
    kilometraje_ingreso: int
    estado: EstadoOrdenTrabajo = EstadoOrdenTrabajo.PENDIENTE
    id: int | None = None
