from typing import List

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from proyectobackend.routers.dependencies import get_vehiculo_service
from proyectobackend.schemas.error import ErrorDetail, ErrorResponse
from proyectobackend.schemas.vehiculo import (
    VehiculoCreate,
    VehiculoResponse,
    VehiculoUpdate,
)
from proyectobackend.services.vehiculo_service import VehiculoService


router = APIRouter(
    prefix="/vehiculos",
    tags=["Vehiculos"],
    responses={
        422: {"model": ErrorResponse},
    },
)


def _formatear_error(ex: Exception) -> JSONResponse:
    mensaje_completo = str(ex)

    if ":" in mensaje_completo:
        code, message = mensaje_completo.split(":", 1)
    else:
        code = "VEHICLE_ERROR"
        message = mensaje_completo

    status_code = status.HTTP_400_BAD_REQUEST

    if code in [
        "CLIENT_NOT_FOUND",
        "VEHICLE_NOT_FOUND",
    ]:
        status_code = status.HTTP_404_NOT_FOUND

    elif code in [
        "VEHICLE_LICENSE_PLATE_ALREADY_EXISTS",
        "VEHICLE_HAS_WORK_ORDERS",
    ]:
        status_code = status.HTTP_409_CONFLICT

    respuesta = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message.strip(),
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=respuesta.model_dump(),
    )


@router.post(
    "/",
    response_model=VehiculoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Crear un vehículo",
    description=(
        "Registra patente de seis caracteres, marca, modelo, año, kilometraje "
        "e ID de un cliente existente. Devuelve 404 si el cliente no existe y "
        "409 si la patente está registrada."
    ),
)
def crear_vehiculo(
    vehiculo: VehiculoCreate,
    vehiculo_service: VehiculoService = Depends(get_vehiculo_service),
):
    try:
        return vehiculo_service.crear_vehiculo(vehiculo)

    except (LookupError, ValueError) as error:
        return _formatear_error(error)


@router.get(
    "/",
    response_model=List[VehiculoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar vehículos",
    description=(
        "Devuelve los vehículos registrados. Cada elemento incluye su "
        "identificador y el ID del cliente asociado."
    ),
)
def listar_vehiculos(
    vehiculo_service: VehiculoService = Depends(get_vehiculo_service),
):
    return vehiculo_service.listar_vehiculos()


@router.get(
    "/{vehiculo_id}",
    response_model=VehiculoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse},
    },
    summary="Obtener un vehículo por ID",
    description=(
        "Consulta un vehículo por su identificador numérico. Devuelve 404 si "
        "no existe."
    ),
)
def obtener_vehiculo(
    vehiculo_id: int,
    vehiculo_service: VehiculoService = Depends(get_vehiculo_service),
):
    try:
        return vehiculo_service.obtener_vehiculo_por_id(vehiculo_id)

    except LookupError as error:
        return _formatear_error(error)


@router.patch(
    "/{vehiculo_id}",
    response_model=VehiculoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Actualizar parcialmente un vehículo",
    description=(
        "Actualiza únicamente los campos enviados. Valida el cliente y la "
        "unicidad de la patente; devuelve 404 si falta el vehículo o cliente "
        "y 409 ante una patente duplicada."
    ),
)
def actualizar_vehiculo(
    vehiculo_id: int,
    vehiculo_data: VehiculoUpdate,
    vehiculo_service: VehiculoService = Depends(get_vehiculo_service),
):
    try:
        return vehiculo_service.actualizar_vehiculo(
            vehiculo_id,
            vehiculo_data,
        )

    except (LookupError, ValueError) as error:
        return _formatear_error(error)


@router.delete(
    "/{vehiculo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Eliminar un vehículo",
    description=(
        "Elimina un vehículo sin órdenes de trabajo y devuelve 204 sin "
        "cuerpo. Devuelve 404 si no existe o 409 si tiene órdenes asociadas."
    ),
)
def eliminar_vehiculo(
    vehiculo_id: int,
    vehiculo_service: VehiculoService = Depends(get_vehiculo_service),
):
    try:
        vehiculo_service.eliminar_vehiculo(vehiculo_id)

        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
        )

    except (LookupError, ValueError) as error:
        return _formatear_error(error)
