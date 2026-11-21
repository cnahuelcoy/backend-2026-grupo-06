"""Composición de servicios para los routers HTTP.

FastAPI resuelve estos proveedores por solicitud. Los repositorios conservan
la gestión de sesiones y transacciones que ya utiliza cada módulo.
"""

from proyectobackend.repositories.cliente_repository import cliente_repo
from proyectobackend.repositories.orden_trabajo_repositorio import (
    orden_trabajo_repository_instance,
)
from proyectobackend.repositories.reparacion_repository import (
    reparacion_repository_instance,
)
from proyectobackend.repositories.vehiculo_repository import (
    vehiculo_repository_instance,
)
from proyectobackend.services.cliente_service import ClienteService
from proyectobackend.services.orden_trabajo_services import OrdenTrabajoService
from proyectobackend.services.reparacion_service import ReparacionService
from proyectobackend.services.vehiculo_service import VehiculoService


def get_cliente_service() -> ClienteService:
    return ClienteService(cliente_repo)


def get_vehiculo_service() -> VehiculoService:
    return VehiculoService(vehiculo_repository_instance, cliente_repo)


def get_orden_trabajo_service() -> OrdenTrabajoService:
    return OrdenTrabajoService(
        orden_trabajo_repository_instance,
        vehiculo_repository_instance,
    )


def get_reparacion_service() -> ReparacionService:
    return ReparacionService(
        repository=reparacion_repository_instance,
        orden_repository=orden_trabajo_repository_instance,
    )
