from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import unittest
from unittest.mock import Mock

import jwt
from sqlalchemy import create_engine, text

from proyectobackend.domain.usuario import RolUsuario, Usuario
from proyectobackend.repositories.usuario_repository import UsuarioRepository
from proyectobackend.repositories.sesion_repository import SesionRepository
from proyectobackend.schemas.autenticacion import UsuarioLogin, UsuarioRegistro
from proyectobackend.security.config import ConfiguracionJWT
from proyectobackend.security.jwt_service import JWTService, TokenInvalido
from proyectobackend.security.password_hasher import PasswordHasher
from proyectobackend.services.auth_service import AuthService, CredencialesInvalidas
from tests.soporte_api import ApiDePrueba
from tests.test_usuarios_sesiones import BaseUsuariosSesiones


class TestSeguridadAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hasher = PasswordHasher()
        cls.password = secrets.token_urlsafe(24)
        cls.hash = cls.hasher.hashear(cls.password)

    def setUp(self):
        self.config = ConfiguracionJWT(secrets.token_urlsafe(48))
        self.tokens = JWTService(self.config)
        self.usuario = Usuario(1, "operador@example.com", self.hash)

    def claims(self):
        ahora = int(datetime.now(timezone.utc).timestamp())
        return {
            "sub": "1",
            "type": "access",
            "ver": 0,
            "iat": ahora,
            "exp": ahora + 900,
        }

    def test_hash_argon2id_salt_y_verificacion(self):
        otro = self.hasher.hashear(self.password)
        self.assertTrue(self.hash.startswith("$argon2id$"))
        self.assertNotEqual(self.hash, otro)
        self.assertTrue(self.hasher.verificar(self.password, self.hash))
        self.assertFalse(self.hasher.verificar("incorrecta", self.hash))
        self.assertFalse(self.hasher.verificar(self.password, "hash-invalido"))
        with self.assertRaises(ValueError):
            self.hasher.hashear("corta")

    def test_access_valido_corto_y_sin_datos_sensibles(self):
        token = self.tokens.emitir_access(self.usuario)
        self.assertEqual(self.tokens.validar_access(token), (1, 0))
        claims = jwt.decode(token, self.config.secret, algorithms=["HS256"])
        self.assertEqual(set(claims), {"sub", "exp", "iat", "type", "ver"})
        self.assertEqual(claims["exp"] - claims["iat"], 900)
        self.assertNotIn(self.hash, token)

    def test_rechaza_firma_algoritmo_proposito_y_expiracion(self):
        for cambios, clave, algoritmo in (
            ({}, secrets.token_urlsafe(48), "HS256"),
            ({}, self.config.secret, "HS384"),
            ({"type": "refresh"}, self.config.secret, "HS256"),
            ({"type": "reset"}, self.config.secret, "HS256"),
            ({"iat": 1, "exp": 2}, self.config.secret, "HS256"),
        ):
            with (
                self.subTest(cambios=cambios, algoritmo=algoritmo),
                self.assertRaises(TokenInvalido),
            ):
                self.tokens.validar_access(
                    jwt.encode({**self.claims(), **cambios}, clave, algorithm=algoritmo)
                )
        token = self.tokens.emitir_access(self.usuario)
        partes = token.split(".")
        partes[1] = partes[1][:-1] + ("a" if partes[1][-1] != "a" else "b")
        with self.assertRaises(TokenInvalido):
            self.tokens.validar_access(".".join(partes))

    def test_rechaza_claims_ausentes_o_con_tipos_invalidos(self):
        for campo in self.claims():
            claims = self.claims()
            del claims[campo]
            with self.subTest(falta=campo), self.assertRaises(TokenInvalido):
                self.tokens.validar_access(
                    jwt.encode(claims, self.config.secret, algorithm="HS256")
                )
        for cambios in (
            {"sub": "0"},
            {"sub": "99999999999"},
            {"sub": "x"},
            {"ver": True},
            {"ver": -1},
            {"exp": "9999999999"},
        ):
            with self.subTest(cambios=cambios), self.assertRaises(TokenInvalido):
                self.tokens.validar_access(
                    jwt.encode(
                        {**self.claims(), **cambios},
                        self.config.secret,
                        algorithm="HS256",
                    )
                )

    def test_secreto_y_duracion_no_tienen_valores_inseguros_por_defecto(self):
        for clave in ("", "corta", "CAMBIAR_" + "x" * 40):
            with self.assertRaises(ValueError):
                ConfiguracionJWT(clave)
        with self.assertRaises(ValueError):
            ConfiguracionJWT(self.config.secret, 999)
        self.assertNotIn(self.config.secret, repr(self.config))

    def test_registro_fuerza_operador_y_entrega_hash_al_repositorio(self):
        usuarios = Mock()
        servicio = AuthService(usuarios, self.hasher, self.tokens)
        servicio.registrar(
            UsuarioRegistro(email="NUEVO@example.com", password=self.password)
        )
        email, hash_guardado, rol = usuarios.crear.call_args.args
        self.assertEqual((email, rol), ("nuevo@example.com", RolUsuario.OPERADOR))
        self.assertTrue(self.hasher.verificar(self.password, hash_guardado))

    def test_cuenta_inexistente_verifica_hash_ficticio_y_no_emite_token(self):
        usuarios, hasher, tokens = Mock(), Mock(), Mock()
        usuarios.buscar_por_email.return_value = None
        hasher.hash_ficticio = "hash-ficticio"
        servicio = AuthService(usuarios, hasher, tokens)
        with self.assertRaises(CredencialesInvalidas):
            servicio.login(
                UsuarioLogin(email="nadie@example.com", password="incorrecta")
            )
        hasher.verificar.assert_called_once_with("incorrecta", "hash-ficticio")
        tokens.emitir_access.assert_not_called()


class TestAutenticacionHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = ApiDePrueba(autenticar=False)
        cls.addClassCleanup(cls.api.cerrar)
        cls.api.iniciar()

    def setUp(self):
        self.email = secrets.token_hex(8) + "@example.com"
        self.password = secrets.token_urlsafe(24)
        self.datos = {"email": self.email, "password": self.password}

    def registrar(self):
        estado, usuario = self.api.solicitar("POST", "/auth/registro", self.datos)
        self.assertEqual(estado, 201)
        self.assertEqual(set(usuario), {"id", "email", "rol", "activo"})
        return usuario

    def login(self):
        estado, cuerpo = self.api.solicitar("POST", "/auth/login", self.datos)
        self.assertEqual(estado, 200)
        return {"Authorization": "Bearer " + cuerpo["access_token"]}

    def consultar_sql(self, sentencia, parametros):
        engine = create_engine("sqlite:///" + str(self.api.base_de_datos))
        try:
            with engine.begin() as conexion:
                resultado = conexion.execute(text(sentencia), parametros)
                return resultado.mappings().all() if resultado.returns_rows else None
        finally:
            engine.dispose()

    def test_registro_login_me_y_persistencia(self):
        usuario = self.registrar()
        cabeceras = self.login()
        self.assertEqual(
            self.api.solicitar("GET", "/auth/me", headers=cabeceras), (200, usuario)
        )
        filas = self.consultar_sql(
            "SELECT password_hash, rol FROM usuarios WHERE email = :email",
            {"email": self.email},
        )
        self.assertTrue(filas[0]["password_hash"].startswith("$argon2id$"))
        self.assertEqual(filas[0]["rol"], "operador")
        self.assertNotEqual(filas[0]["password_hash"], self.password)

    def test_credenciales_erroneas_cuenta_inactiva_e_inexistente_error_generico(self):
        usuario = self.registrar()
        _, error = self.api.solicitar(
            "POST", "/auth/login", {**self.datos, "password": "incorrecta"}
        )
        estado, inexistente = self.api.solicitar(
            "POST", "/auth/login", {**self.datos, "email": "no-existe@example.com"}
        )
        self.assertEqual(estado, 401)
        self.assertEqual(error, inexistente)
        self.consultar_sql(
            "UPDATE usuarios SET activo = false WHERE id = :id", {"id": usuario["id"]}
        )
        self.assertEqual(
            self.api.solicitar("POST", "/auth/login", self.datos), (401, error)
        )

    def test_bloqueo_persistente_tras_cinco_fallos_y_desbloqueo(self):
        usuario = self.registrar()
        for _ in range(5):
            self.assertEqual(
                self.api.solicitar(
                    "POST", "/auth/login", {**self.datos, "password": "incorrecta"}
                )[0],
                401,
            )
        self.assertEqual(self.api.solicitar("POST", "/auth/login", self.datos)[0], 401)
        filas = self.consultar_sql(
            "SELECT bloqueado_hasta FROM usuarios WHERE id = :id", {"id": usuario["id"]}
        )
        self.assertIsNotNone(filas[0]["bloqueado_hasta"])
        self.consultar_sql(
            "UPDATE usuarios SET bloqueado_hasta = :fecha WHERE id = :id",
            {
                "fecha": datetime.now(timezone.utc) - timedelta(minutes=1),
                "id": usuario["id"],
            },
        )
        self.login()
        filas = self.consultar_sql(
            "SELECT intentos_fallidos, bloqueado_hasta FROM usuarios WHERE id = :id",
            {"id": usuario["id"]},
        )
        self.assertEqual(
            dict(filas[0]), {"intentos_fallidos": 0, "bloqueado_hasta": None}
        )

    def test_proteccion_de_los_cuatro_modulos_y_dos_roles(self):
        usuario = self.registrar()
        operador = self.login()
        for ruta in ("/clientes", "/vehiculos/", "/ordenes-trabajo", "/reparaciones/"):
            with self.subTest(ruta=ruta):
                estado, error = self.api.solicitar("GET", ruta)
                self.assertEqual(estado, 401)
                self.assertEqual(error["error"]["message"], "Acceso bloqueado")
                self.assertEqual(
                    self.api.solicitar("GET", ruta, headers=operador)[0], 200
                )
        for ruta in ("/clientes/999999", "/vehiculos/999999", "/reparaciones/999999"):
            with self.subTest(ruta=ruta):
                estado, error = self.api.solicitar("DELETE", ruta, headers=operador)
                self.assertEqual(estado, 403)
                self.assertEqual(error["error"]["message"], "Acceso bloqueado")
        email_admin = "admin-" + self.email
        self.consultar_sql(
            "INSERT INTO usuarios (email, password_hash, rol, activo, version_tokens, intentos_fallidos) "
            "SELECT :email, password_hash, 'admin', true, 0, 0 FROM usuarios WHERE id = :id",
            {"email": email_admin, "id": usuario["id"]},
        )
        estado, identidad = self.api.solicitar(
            "POST",
            "/auth/login",
            {
                "email": email_admin,
                "password": self.password,
            },
        )
        self.assertEqual(estado, 200)
        admin = {"Authorization": "Bearer " + identidad["access_token"]}
        estado, cliente = self.api.solicitar(
            "POST",
            "/clientes",
            {
                "nombre": "Ana",
                "apellido": "Prueba",
                "email": self.email,
                "telefono": "+56912345678",
                "direccion": "Calle Prueba 123",
            },
            headers=operador,
        )
        self.assertEqual(estado, 201)
        ruta = "/clientes/" + str(cliente["id"])
        self.assertEqual(self.api.solicitar("DELETE", ruta, headers=operador)[0], 403)
        self.assertEqual(self.api.solicitar("GET", ruta, headers=operador)[0], 200)
        self.assertEqual(self.api.solicitar("DELETE", ruta, headers=admin)[0], 204)
        self.assertEqual(self.api.solicitar("GET", ruta, headers=admin)[0], 404)

    def test_token_vencido_alterado_otro_proposito_y_version_revocada(self):
        usuario = self.registrar()
        cabeceras = self.login()
        ahora = int(datetime.now(timezone.utc).timestamp())
        claims = {
            "sub": str(usuario["id"]),
            "ver": 0,
            "type": "access",
            "iat": ahora,
            "exp": ahora + 900,
        }
        for cambios in (
            {"iat": 1, "exp": 2},
            {"type": "reset"},
            {"type": "refresh"},
            {"sub": "999999"},
        ):
            token = jwt.encode(
                {**claims, **cambios}, self.api.secreto_jwt, algorithm="HS256"
            )
            self.assertEqual(
                self.api.solicitar(
                    "GET", "/auth/me", headers={"Authorization": "Bearer " + token}
                )[0],
                401,
            )
        self.assertEqual(
            self.api.solicitar(
                "GET", "/auth/me", headers={"Authorization": "Bearer invalid"}
            )[0],
            401,
        )
        self.consultar_sql(
            "UPDATE usuarios SET version_tokens = version_tokens + 1 WHERE id = :id",
            {"id": usuario["id"]},
        )
        self.assertEqual(
            self.api.solicitar("GET", "/auth/me", headers=cabeceras)[0], 401
        )

    def test_no_acepta_privilegios_ni_refleja_password_en_errores(self):
        for cambios in (
            {"rol": "admin"},
            {"activo": True},
            {"password": "corta"},
            {"password": {"valor": self.password}},
        ):
            estado, error = self.api.solicitar(
                "POST", "/auth/registro", {**self.datos, **cambios}
            )
            self.assertEqual(estado, 422)
            self.assertNotIn(self.password, json.dumps(error))
            self.assertTrue(
                all(
                    set(detalle) <= {"loc", "type", "msg"}
                    for detalle in error["error"]["details"]
                )
            )
        self.registrar()
        self.assertEqual(
            self.api.solicitar(
                "POST", "/auth/registro", {**self.datos, "email": self.email.upper()}
            )[0],
            409,
        )

    def test_openapi_declara_bearer_en_negocio_y_no_en_login(self):
        estado, documento = self.api.solicitar("GET", "/openapi.json")
        self.assertEqual(estado, 200)
        self.assertIn("HTTPBearer", documento["components"]["securitySchemes"])
        self.assertTrue(documento["paths"]["/clientes"]["get"]["security"])
        self.assertNotIn("security", documento["paths"]["/auth/login"]["post"])


class TestPersistenciaAuth(BaseUsuariosSesiones):
    @classmethod
    def preparar(cls):
        cls.hasher = PasswordHasher()
        cls.password = secrets.token_urlsafe(24)
        cls.hash = cls.hasher.hashear(cls.password)
        cls.alembic("upgrade", "0002")
        with cls.engine.begin() as conexion:
            conexion.execute(
                text(
                    "INSERT INTO usuarios (email, password_hash, rol, activo, version_tokens) "
                    "VALUES (:email, :hash, 'admin', true, 3)"
                ),
                {"email": "anterior@example.com", "hash": cls.hash},
            )
        cls.alembic("upgrade", "head")

    def setUp(self):
        self.usuarios = UsuarioRepository(self.factory)
        self.usuario = self.usuarios.crear(
            secrets.token_hex(8) + "@example.com", self.hash
        )
        self.tokens = JWTService(ConfiguracionJWT(secrets.token_urlsafe(48)))
        self.servicio = AuthService(self.usuarios, self.hasher, self.tokens)

    def test_migracion_0003_conserva_usuario_anterior_y_coincide_con_modelos(self):
        usuario = self.usuarios.buscar_por_email("anterior@example.com")
        self.assertEqual(usuario.rol, RolUsuario.ADMIN)
        self.assertEqual(usuario.version_tokens, 3)
        self.assertEqual(usuario.password_hash, self.hash)
        self.assertEqual(usuario.intentos_fallidos, 0)
        self.assertIsNone(usuario.bloqueado_hasta)
        self.assertIn("No new upgrade operations", self.alembic("check"))

    def test_cinco_fallos_simultaneos_no_pierden_el_contador(self):
        ahora = datetime.now(timezone.utc)
        with ThreadPoolExecutor(max_workers=5) as ejecutor:
            list(
                ejecutor.map(
                    lambda _: self.usuarios.registrar_login(
                        self.usuario.id, False, 0, ahora
                    ),
                    range(5),
                )
            )
        actual = self.usuarios.buscar_por_id(self.usuario.id)
        self.assertEqual(actual.intentos_fallidos, 0)
        self.assertEqual(actual.bloqueado_hasta, ahora + timedelta(minutes=15))
        self.assertIsNone(self.usuarios.registrar_login(actual.id, True, 0, ahora))

    def test_login_correcto_limpia_fallos_persistidos(self):
        ahora = datetime.now(timezone.utc)
        self.usuarios.registrar_login(self.usuario.id, False, 0, ahora)
        token = self.servicio.login(
            UsuarioLogin(email=self.usuario.email, password=self.password)
        )
        self.assertEqual(self.tokens.validar_access(token), (self.usuario.id, 0))
        self.assertEqual(
            self.usuarios.buscar_por_id(self.usuario.id).intentos_fallidos, 0
        )

    def test_login_no_acepta_snapshot_anterior_al_cambio_de_password(self):
        self.usuarios.cambiar_password_hash(self.usuario.id, self.hash)
        self.assertIsNone(
            self.usuarios.registrar_login(
                self.usuario.id, True, 0, datetime.now(timezone.utc)
            )
        )

    def test_login_rechaza_cuenta_desactivada_sin_emitir_token(self):
        self.usuarios.desactivar(self.usuario.id)
        with self.assertRaises(CredencialesInvalidas):
            self.servicio.login(
                UsuarioLogin(email=self.usuario.email, password=self.password)
            )

    def test_fallos_y_bloqueo_sobreviven_a_otro_repositorio(self):
        self.usuarios.registrar_login(
            self.usuario.id, False, 0, datetime.now(timezone.utc)
        )
        self.assertEqual(
            UsuarioRepository(self.factory)
            .buscar_por_id(self.usuario.id)
            .intentos_fallidos,
            1,
        )

    def test_admin_configurado_se_crea_con_hash_y_es_idempotente(self):
        email = "admin-" + self.usuario.email
        primero = self.servicio.asegurar_admin(email, self.password)
        self.usuarios.registrar_login(primero.id, False, 0, datetime.now(timezone.utc))
        segundo = self.servicio.asegurar_admin(email, self.password)
        self.assertEqual(primero.id, segundo.id)
        self.assertEqual(segundo.rol, RolUsuario.ADMIN)
        self.assertTrue(segundo.activo)
        self.assertEqual(primero.password_hash, segundo.password_hash)
        self.assertEqual(segundo.version_tokens, 0)
        self.assertEqual(segundo.intentos_fallidos, 1)
        self.assertTrue(self.hasher.verificar(self.password, segundo.password_hash))

    def test_cambiar_admin_configurado_actualiza_hash_y_revoca_sesiones(self):
        admin = self.servicio.asegurar_admin(
            "admin-" + self.usuario.email, self.password
        )
        sesiones = SesionRepository(self.factory)
        sesiones.crear(
            admin.id, "a" * 64, datetime.now(timezone.utc) + timedelta(days=1), 0
        )
        nueva = secrets.token_urlsafe(24)
        actualizado = self.servicio.asegurar_admin(admin.email, nueva)
        self.assertEqual(actualizado.id, admin.id)
        self.assertEqual(actualizado.version_tokens, 1)
        self.assertTrue(self.hasher.verificar(nueva, actualizado.password_hash))
        self.assertFalse(
            self.hasher.verificar(self.password, actualizado.password_hash)
        )
        self.assertIsNotNone(sesiones.buscar_por_hash("a" * 64).revocada_en)

    def test_admin_existente_se_activa_y_se_promueve_desde_configuracion(self):
        actualizado = self.servicio.asegurar_admin(self.usuario.email, self.password)
        self.assertEqual(actualizado.id, self.usuario.id)
        self.assertEqual(actualizado.rol, RolUsuario.ADMIN)
        self.assertEqual(actualizado.version_tokens, 1)
        self.usuarios.desactivar(actualizado.id)
        reactivado = self.servicio.asegurar_admin(actualizado.email, self.password)
        self.assertTrue(reactivado.activo)
        self.assertEqual(reactivado.version_tokens, 3)

    def test_snapshot_admin_antiguo_no_sobrescribe_cambio_de_credencial(self):
        nuevo_hash = self.hasher.hashear(secrets.token_urlsafe(24))
        self.usuarios.cambiar_password_hash(self.usuario.id, nuevo_hash)
        self.assertIsNone(self.usuarios.sincronizar_admin(self.usuario, self.hash))
        actual = self.usuarios.buscar_por_id(self.usuario.id)
        self.assertEqual(actual.password_hash, nuevo_hash)
        self.assertEqual(actual.rol, RolUsuario.OPERADOR)

    def test_dos_arranques_no_duplican_admin_ni_invalidan_version_sin_cambios(self):
        email = "admin-" + self.usuario.email
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            usuarios = list(
                ejecutor.map(
                    lambda _: self.servicio.asegurar_admin(email, self.password),
                    range(2),
                )
            )
        self.assertEqual(usuarios[0].id, usuarios[1].id)
        self.assertEqual(self.usuarios.buscar_por_email(email).version_tokens, 0)

    def test_configuracion_admin_invalida_no_refleja_password(self):
        for email, password in (
            ("correo-invalido", self.password),
            (self.usuario.email, "corta"),
        ):
            with self.assertRaises(ValueError) as error:
                self.servicio.asegurar_admin(email, password)
            self.assertNotIn(password, str(error.exception))


class TestAdminDesdeEntorno(unittest.TestCase):
    def test_arranque_crea_admin_y_cambio_de_password_revoca_access(self):
        password = secrets.token_urlsafe(24)
        api = ApiDePrueba(
            autenticar=False, admin_email="admin@example.com", admin_password=password
        )
        self.addCleanup(api.cerrar)
        api.iniciar()

        def login(clave):
            return api.solicitar(
                "POST", "/auth/login", {"email": api.admin_email, "password": clave}
            )

        estado, identidad = login(password)
        self.assertEqual(estado, 200)
        cabeceras = {"Authorization": "Bearer " + identidad["access_token"]}
        estado, usuario = api.solicitar("GET", "/auth/me", headers=cabeceras)
        self.assertEqual(estado, 200)
        self.assertEqual(usuario["rol"], "admin")
        api.reiniciar()
        self.assertEqual(api.solicitar("GET", "/auth/me", headers=cabeceras)[0], 200)
        api.admin_password = secrets.token_urlsafe(24)
        api.reiniciar()
        self.assertEqual(api.solicitar("GET", "/auth/me", headers=cabeceras)[0], 401)
        self.assertEqual(login(password)[0], 401)
        self.assertEqual(login(api.admin_password)[0], 200)

    def test_sin_password_configurada_no_se_crea_admin(self):
        api = ApiDePrueba(autenticar=False, admin_email="admin@example.com")
        self.addCleanup(api.cerrar)
        api.iniciar()
        self.assertEqual(
            api.solicitar(
                "POST",
                "/auth/registro",
                {
                    "email": api.admin_email,
                    "password": secrets.token_urlsafe(24),
                },
            )[0],
            201,
        )

    def test_error_de_arranque_no_muestra_password_configurada(self):
        password = secrets.token_urlsafe(24)
        api = ApiDePrueba(
            autenticar=False, admin_email="correo-invalido", admin_password=password
        )
        self.addCleanup(api.cerrar)
        with self.assertRaises(RuntimeError) as error:
            api.iniciar()
        self.assertNotIn(password, str(error.exception))
