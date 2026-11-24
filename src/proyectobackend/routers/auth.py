from fastapi import APIRouter, Depends, HTTPException, Response, status

from proyectobackend.domain.usuario import EmailUsuarioDuplicado, Usuario
from proyectobackend.routers.auth_dependencies import get_auth_service, get_usuario_actual
from proyectobackend.schemas.autenticacion import TokenResponse, UsuarioLogin, UsuarioRegistro, UsuarioResponse
from proyectobackend.schemas.error import ErrorResponse
from proyectobackend.services.auth_service import AuthService, CredencialesInvalidas


router = APIRouter(prefix="/auth", tags=["Autenticación"], responses={422: {"model": ErrorResponse}})


@router.post(
    "/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED,
    summary="Registrar un operador", description="Crea una cuenta con correo único y contraseña de 12 a 128 caracteres. No permite elegir privilegios.",
    responses={409: {"model": ErrorResponse}},
)
def registro(datos: UsuarioRegistro, servicio: AuthService = Depends(get_auth_service)):
    try:
        return servicio.registrar(datos)
    except EmailUsuarioDuplicado:
        raise HTTPException(status_code=409, detail={
            "code": "USER_EMAIL_ALREADY_EXISTS", "message": "El identificador ya está registrado", "details": [],
        }) from None


@router.post(
    "/login", response_model=TokenResponse, summary="Iniciar sesión",
    description="Valida credenciales y emite un access JWT de corta duración. Cinco fallos bloquean el acceso durante 15 minutos; el error es genérico.",
    responses={401: {"model": ErrorResponse}},
)
def login(datos: UsuarioLogin, response: Response, servicio: AuthService = Depends(get_auth_service)):
    try:
        token = servicio.login(datos)
    except CredencialesInvalidas:
        raise HTTPException(status_code=401, detail={
            "code": "INVALID_CREDENTIALS", "message": "Credenciales incorrectas o cuenta no disponible", "details": [],
        }, headers={"WWW-Authenticate": "Bearer"}) from None
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=token)


@router.get(
    "/me", response_model=UsuarioResponse, summary="Consultar mi cuenta",
    description="Devuelve la identidad del Bearer validado. Rechaza cuentas inactivas y versiones de token revocadas.",
    responses={401: {"model": ErrorResponse}},
)
def me(usuario: Usuario = Depends(get_usuario_actual)):
    return usuario
