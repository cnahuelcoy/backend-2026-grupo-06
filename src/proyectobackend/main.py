from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from proyectobackend.database.init_db import init_db
from proyectobackend.routers.auth import router as auth_router
from proyectobackend.routers.auth_dependencies import (
    autorizar_negocio,
    get_jwt_service,
    get_password_hasher,
    get_usuario_repository,
)
from proyectobackend.services.auth_service import AuthService
from proyectobackend.routers.clientes import router as clientes_router
from proyectobackend.routers.vehiculos import router as vehiculos_router
from proyectobackend.routers.reparaciones import router as reparaciones_router
from proyectobackend.routers.orden_trabajo_routers import (
    router as orden_trabajo_router,
)
from proyectobackend.schemas.error import ErrorDetail, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_jwt_service()
    init_db()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if admin_password:
        AuthService(
            get_usuario_repository(), get_password_hasher(), get_jwt_service()
        ).asegurar_admin(
            os.getenv("ADMIN_EMAIL", ""),
            admin_password,
        )
    yield


app = FastAPI(
    title="API Taller Mecánico",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    respuesta = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Los datos de la solicitud no son válidos",
            details=jsonable_encoder(
                [
                    {
                        clave: error[clave]
                        for clave in ("loc", "type", "msg")
                        if clave in error
                    }
                    for error in exc.errors()
                ]
            ),
        )
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=respuesta.model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
            headers=exc.headers,
        )
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )


app.include_router(auth_router)
for router in (
    clientes_router,
    vehiculos_router,
    reparaciones_router,
    orden_trabajo_router,
):
    app.include_router(
        router,
        dependencies=[Depends(autorizar_negocio)],
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
        },
    )


@app.get("/")
def root():
    return {"mensaje": "API Taller Mecánico funcionando"}
