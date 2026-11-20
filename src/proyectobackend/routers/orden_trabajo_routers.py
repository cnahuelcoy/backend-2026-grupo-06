from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from proyectobackend.domain.orden_trabajo import EstadoOrdenTrabajo
from proyectobackend.routers.dependencies import get_orden_trabajo_service
from proyectobackend.schemas.error import ErrorDetail, ErrorResponse
from proyectobackend.schemas.orden_trabajo_schemas import (
    OrdenTrabajoCreate,
    OrdenTrabajoListadoResponse,
    OrdenTrabajoResponse,
    OrdenTrabajoUpdate,
)
from proyectobackend.services.orden_trabajo_services import OrdenTrabajoService


router = APIRouter(
    prefix="/ordenes-trabajo",
    tags=["ordenes-trabajo"],
    responses={
        422: {"model": ErrorResponse},
    },
)


def _respuesta_error(
    error: Exception,
    status_code: int,
) -> JSONResponse:
    code, separador, message = str(error).partition(":")

    respuesta = ErrorResponse(
        error=ErrorDetail(
            code=code if separador else "WORK_ORDER_ERROR",
            message=message.strip() if separador else str(error),
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=respuesta.model_dump(),
    )


@router.post(
    "",
    response_model=OrdenTrabajoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
    },
    summary="Crear una orden de trabajo",
    description=(
        "Registra vehículo, fecha de ingreso, descripción del problema y "
        "kilometraje. El estado inicial es pendiente si se omite. Devuelve "
        "404 si el vehículo no existe."
    ),
)
def crear_orden_trabajo(
    datos: OrdenTrabajoCreate,
    service: OrdenTrabajoService = Depends(get_orden_trabajo_service),
):
    try:
        return service.crear(datos)
    except LookupError as error:
        return _respuesta_error(
            error,
            status.HTTP_404_NOT_FOUND,
        )


@router.get(
    "/{orden_id}",
    response_model=OrdenTrabajoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse},
    },
    summary="Obtener una orden de trabajo por ID",
    description=(
        "Consulta una orden por su identificador numérico. Devuelve 404 si no "
        "existe."
    ),
)
def obtener_orden_trabajo(
    orden_id: int,
    service: OrdenTrabajoService = Depends(get_orden_trabajo_service),
):
    try:
        return service.obtener_por_id(orden_id)
    except LookupError as error:
        return _respuesta_error(
            error,
            status.HTTP_404_NOT_FOUND,
        )


@router.get(
    "",
    response_model=OrdenTrabajoListadoResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar órdenes de trabajo",
    description=(
        "Filtra por estado, ordena por ID, fecha o kilometraje de ingreso y "
        "pagina el resultado. Devuelve items, total, página, límite y total "
        "de páginas; el límite admite de 1 a 100 registros."
    ),
)
def listar_ordenes_trabajo(
    estado: EstadoOrdenTrabajo | None = None,
    ordenar_por: Literal[
        "id",
        "fecha_ingreso",
        "kilometraje_ingreso",
    ] = "id",
    direccion: Literal["asc", "desc"] = "asc",
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=100),
    service: OrdenTrabajoService = Depends(get_orden_trabajo_service),
):
    return service.listar(
        estado=estado,
        ordenar_por=ordenar_por,
        direccion=direccion,
        pagina=pagina,
        limite=limite,
    )


@router.patch(
    "/{orden_id}",
    response_model=OrdenTrabajoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Actualizar parcialmente una orden de trabajo",
    description=(
        "Actualiza solo los campos enviados y valida el vehículo asociado. "
        "Devuelve 404 si falta la orden o el vehículo, 409 al intentar "
        "reabrir una orden finalizada."
    ),
)
def actualizar_orden_trabajo(
    orden_id: int,
    datos: OrdenTrabajoUpdate,
    service: OrdenTrabajoService = Depends(get_orden_trabajo_service),
):
    try:
        return service.actualizar(
            orden_id,
            datos,
        )
    except LookupError as error:
        return _respuesta_error(
            error,
            status.HTTP_404_NOT_FOUND,
        )
    except ValueError as error:
        code = str(error).partition(":")[0]

        if code == "INVALID_WORK_ORDER_STATE":
            return _respuesta_error(
                error,
                status.HTTP_409_CONFLICT,
            )

        return _respuesta_error(
            error,
            status.HTTP_400_BAD_REQUEST,
        )
