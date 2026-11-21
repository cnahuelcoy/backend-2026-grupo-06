
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from proyectobackend.routers.dependencies import get_cliente_service
from proyectobackend.schemas.cliente import (
    ClienteCreate,
    ClienteListadoResponse,
    ClienteResponse,
    ClienteUpdate,
)
from proyectobackend.schemas.error import ErrorDetail, ErrorResponse
from proyectobackend.services.cliente_service import ClienteService


router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"],
    responses={
        422: {"model": ErrorResponse},
    },
)


def crear_error(
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    error = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(),
    )


@router.post(
    "",
    response_model=ClienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un cliente",
    responses={
        409: {"model": ErrorResponse},
    },
    description=(
        "Registra nombre, apellido, teléfono, correo y dirección. El correo "
        "debe ser único; devuelve 409 si ya está registrado."
    ),
)
def crear_cliente(
    datos: ClienteCreate,
    service: ClienteService = Depends(get_cliente_service),
):
    try:
        return service.crear(datos)
    except ValueError as error:
        return crear_error(
            status_code=status.HTTP_409_CONFLICT,
            code="CLIENT_EMAIL_ALREADY_EXISTS",
            message=str(error),
        )


@router.get(
    "",
    response_model=ClienteListadoResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar clientes",
    description=(
        "Lista clientes permitiendo filtrado por nombre, "
        "ordenamiento y paginación."
    ),
)
def listar_clientes(
    nombre: str | None = Query(
        default=None,
        min_length=2,
        max_length=50,
    ),
    ordenar_por: Literal[
        "id",
        "nombre",
        "apellido",
        "email",
    ] = Query(default="id"),
    direccion: Literal["asc", "desc"] = Query(default="asc"),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=100),
    service: ClienteService = Depends(get_cliente_service),
):
    return service.listar(
        nombre=nombre,
        ordenar_por=ordenar_por,
        direccion=direccion,
        pagina=pagina,
        limite=limite,
    )


@router.get(
    "/{cliente_id}",
    response_model=ClienteResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener un cliente por ID",
    responses={
        404: {"model": ErrorResponse},
    },
    description=(
        "Consulta un cliente por su identificador numérico. Devuelve 404 si "
        "no existe."
    ),
)
def obtener_cliente(
    cliente_id: int,
    service: ClienteService = Depends(get_cliente_service),
):
    cliente = service.obtener_por_id(cliente_id)

    if cliente is None:
        return crear_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CLIENT_NOT_FOUND",
            message="Cliente no encontrado",
        )

    return cliente


@router.patch(
    "/{cliente_id}",
    response_model=ClienteResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar parcialmente un cliente",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    description=(
        "Modifica solo los campos enviados del cliente indicado. Conserva los "
        "restantes; devuelve 404 si no existe y 409 si el correo pertenece a "
        "otro cliente."
    ),
)
def actualizar_cliente(
    cliente_id: int,
    datos: ClienteUpdate,
    service: ClienteService = Depends(get_cliente_service),
):
    try:
        cliente = service.actualizar(cliente_id, datos)
    except ValueError as error:
        return crear_error(
            status_code=status.HTTP_409_CONFLICT,
            code="CLIENT_EMAIL_ALREADY_EXISTS",
            message=str(error),
        )

    if cliente is None:
        return crear_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CLIENT_NOT_FOUND",
            message="Cliente no encontrado",
        )

    return cliente


@router.delete(
    "/{cliente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un cliente",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    description=(
        "Elimina un cliente sin vehículos asociados y devuelve 204 sin "
        "cuerpo. Devuelve 404 si no existe o 409 si todavía tiene vehículos."
    ),
)
def eliminar_cliente(
    cliente_id: int,
    service: ClienteService = Depends(get_cliente_service),
):
    try:
        eliminado = service.eliminar(cliente_id)
    except ValueError as error:
        return crear_error(
            status_code=status.HTTP_409_CONFLICT,
            code="CLIENT_HAS_VEHICLES",
            message=str(error),
        )

    if not eliminado:
        return crear_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CLIENT_NOT_FOUND",
            message="Cliente no encontrado",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
