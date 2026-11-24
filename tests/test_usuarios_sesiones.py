from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from proyectobackend.domain.usuario import EmailUsuarioDuplicado, RolUsuario, UsuarioNoDisponible
from proyectobackend.models.cliente import ClienteModel
from proyectobackend.models.orden_trabajo import OrdenTrabajoModel
from proyectobackend.models.reparacion import ReparacionModel
from proyectobackend.models.sesion import SesionModel
from proyectobackend.models.usuario import UsuarioModel
from proyectobackend.models.vehiculo import VehiculoModel
from proyectobackend.repositories.sesion_repository import SesionRepository
from proyectobackend.repositories.usuario_repository import UsuarioRepository
from proyectobackend.schemas.autenticacion import UsuarioLogin, UsuarioRegistro, UsuarioResponse


RAIZ = Path(__file__).resolve().parents[1]
HASH_CREDENCIAL = "$argon2id$v=19$m=65536,t=3,p=4$fixture$hash_de_prueba"


class BaseUsuariosSesiones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporal = TemporaryDirectory(prefix="usuarios-sesiones-")
        cls.addClassCleanup(cls.temporal.cleanup)
        postgres_url = os.getenv("TEST_USUARIOS_POSTGRES_URL")
        if postgres_url:
            url_base = make_url(postgres_url)
            if url_base.get_backend_name() != "postgresql":
                raise ValueError("TEST_USUARIOS_POSTGRES_URL debe usar PostgreSQL")
            esquema = "test_usuarios_" + uuid4().hex
            base = create_engine(url_base)
            cls.addClassCleanup(base.dispose)
            with base.begin() as conexion:
                conexion.execute(CreateSchema(esquema))

            def limpiar():
                with base.begin() as conexion:
                    conexion.execute(DropSchema(esquema, cascade=True))

            cls.addClassCleanup(limpiar)
            url = url_base.update_query_dict({"options": "-csearch_path=" + esquema})
        else:
            url = make_url("sqlite:///" + str(Path(cls.temporal.name) / "prueba.db"))
        cls.entorno = os.environ.copy()
        cls.entorno["DATABASE_URL"] = url.render_as_string(hide_password=False)
        cls.entorno["PYTHONDONTWRITEBYTECODE"] = "1"
        cls.engine = create_engine(url)
        cls.addClassCleanup(cls.engine.dispose)
        if cls.engine.dialect.name == "sqlite":
            @event.listens_for(cls.engine, "connect")
            def activar_fk(conexion, registro):
                conexion.execute("PRAGMA foreign_keys = ON")
        cls.factory = sessionmaker(bind=cls.engine, expire_on_commit=False)
        cls.preparar()

    @classmethod
    def alembic(cls, *args):
        resultado = subprocess.run(
            [sys.executable, "-B", "-m", "alembic", *args], cwd=RAIZ,
            env=cls.entorno, capture_output=True, text=True, timeout=35,
        )
        if resultado.returncode:
            raise AssertionError(resultado.stdout + resultado.stderr)
        return resultado.stdout + resultado.stderr


class TestUsuariosSesiones(BaseUsuariosSesiones):
    @classmethod
    def preparar(cls):
        cls.alembic("upgrade", "head")

    def setUp(self):
        with self.factory.begin() as session:
            session.execute(delete(SesionModel))
            session.execute(delete(UsuarioModel))
        self.usuarios = UsuarioRepository(self.factory)
        self.sesiones = SesionRepository(self.factory)
        self.usuario = self.usuarios.crear(" Operador@Example.com ", HASH_CREDENCIAL)

    def crear_sesion(self, sufijo="a", usuario=None):
        usuario = usuario or self.usuario
        return self.sesiones.crear(
            usuario.id, sufijo * 64, datetime.now(timezone.utc) + timedelta(days=1),
            usuario.version_tokens,
        )

    def test_identificador_unico_normalizado_y_rol_inicial(self):
        self.assertEqual(self.usuario.email, "operador@example.com")
        self.assertEqual(self.usuario.rol, RolUsuario.OPERADOR)
        self.assertTrue(self.usuario.activo)
        with self.assertRaises(EmailUsuarioDuplicado):
            self.usuarios.crear("OPERADOR@example.com", HASH_CREDENCIAL)
        self.assertEqual(self.usuarios.buscar_por_email(" OPERADOR@example.com "), self.usuario)

    def test_respuesta_no_expone_credenciales_ni_version(self):
        publico = UsuarioResponse.model_validate(self.usuario).model_dump(mode="json")
        self.assertEqual(set(publico), {"id", "email", "rol", "activo"})
        self.assertNotIn(HASH_CREDENCIAL, repr(self.usuario))
        registro = UsuarioRegistro(email=" NUEVO@Example.com ", password="Clave de prueba 123")
        self.assertEqual(registro.email, "nuevo@example.com")
        self.assertNotIn("password", registro.model_dump())
        self.assertNotIn("Clave de prueba 123", repr(registro))

    def test_registro_no_permite_elegir_privilegios_y_exige_doce_caracteres(self):
        for campo, valor in (("rol", "admin"), ("activo", True), ("version_tokens", 5)):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                UsuarioRegistro(email="nuevo@example.com", password="Clave de prueba 123", **{campo: valor})
        with self.assertRaises(ValidationError):
            UsuarioRegistro(email="nuevo@example.com", password="corta")
        with self.assertRaises(ValidationError):
            UsuarioLogin(email="correo_invalido", password="clave")

    def test_dos_roles_sin_asociacion_obligatoria_a_cliente(self):
        admin = self.usuarios.crear("admin@example.com", HASH_CREDENCIAL, RolUsuario.ADMIN)
        self.assertEqual(self.usuarios.buscar_por_id(admin.id).rol, RolUsuario.ADMIN)
        self.assertNotIn("cliente_id", {col["name"] for col in inspect(self.engine).get_columns("usuarios")})

    def test_persistencia_hash_unico_y_relacion_usuario(self):
        sesion = self.crear_sesion()
        recuperada = SesionRepository(self.factory).buscar_por_hash("a" * 64)
        self.assertEqual(sesion, recuperada)
        self.assertTrue(recuperada.vigente(datetime.now(timezone.utc)))
        self.assertEqual(recuperada.usuario_id, self.usuario.id)
        self.assertNotIn(recuperada.refresh_hash, repr(recuperada))
        with self.assertRaises(IntegrityError):
            self.crear_sesion()
        with self.assertRaises(UsuarioNoDisponible):
            self.sesiones.crear(999999, "b" * 64, sesion.expira_en, 0)
        with self.factory.begin() as session, self.assertRaises(IntegrityError):
            session.add(SesionModel(
                id=str(uuid4()), usuario_id=999999, familia_id=str(uuid4()),
                refresh_hash="c" * 64, version_tokens=0,
                creada_en=datetime.now(timezone.utc), expira_en=sesion.expira_en,
            ))
            session.flush()

    def test_consumo_atomico_y_expiracion(self):
        sesion = self.crear_sesion()
        ahora = datetime.now(timezone.utc)
        self.assertFalse(self.sesiones.consumir(sesion.id, sesion.expira_en))
        self.assertFalse(sesion.vigente(sesion.expira_en))
        self.assertTrue(self.sesiones.consumir(sesion.id, ahora))
        self.assertFalse(self.sesiones.consumir(sesion.id, ahora))
        self.assertFalse(self.sesiones.buscar_por_hash("a" * 64).vigente(ahora))

    def test_dos_consumos_simultaneos_solo_permiten_uno(self):
        sesion = self.crear_sesion()
        barrera = Barrier(2)

        def consumir():
            barrera.wait(timeout=5)
            return self.sesiones.consumir(sesion.id, datetime.now(timezone.utc))

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(lambda _: consumir(), range(2)))
        self.assertEqual(sorted(resultados), [False, True])

    def test_revocar_familia_no_afecta_otras_sesiones(self):
        primera = self.crear_sesion()
        otra = self.crear_sesion("b")
        self.assertEqual(self.sesiones.revocar_familia(primera.familia_id), 1)
        self.assertEqual(self.sesiones.revocar_familia(primera.familia_id), 0)
        self.assertFalse(self.sesiones.consumir(primera.id, datetime.now(timezone.utc)))
        self.assertTrue(self.sesiones.buscar_por_hash(otra.refresh_hash).vigente(datetime.now(timezone.utc)))

    def test_cambio_de_hash_invalida_version_y_todas_las_sesiones(self):
        self.crear_sesion()
        self.crear_sesion("b")
        otro = self.usuarios.crear("otro@example.com", HASH_CREDENCIAL)
        sesion_ajena = self.crear_sesion("c", otro)
        actualizado = self.usuarios.cambiar_password_hash(self.usuario.id, HASH_CREDENCIAL + "nuevo")
        self.assertEqual(actualizado.version_tokens, 1)
        self.assertEqual(actualizado.password_hash, HASH_CREDENCIAL + "nuevo")
        for letra in ("a", "b"):
            self.assertIsNotNone(self.sesiones.buscar_por_hash(letra * 64).revocada_en)
        self.assertIsNone(self.sesiones.buscar_por_hash(sesion_ajena.refresh_hash).revocada_en)
        with self.assertRaises(UsuarioNoDisponible):
            self.crear_sesion("d")
        self.assertTrue(self.crear_sesion("d", actualizado).vigente(datetime.now(timezone.utc)))

    def test_desactivacion_invalida_sesiones_y_rechaza_nuevas(self):
        self.crear_sesion()
        desactivado = self.usuarios.desactivar(self.usuario.id)
        self.assertFalse(desactivado.activo)
        self.assertEqual(desactivado.version_tokens, 1)
        self.assertIsNotNone(self.sesiones.buscar_por_hash("a" * 64).revocada_en)
        with self.assertRaises(UsuarioNoDisponible):
            self.crear_sesion("b", desactivado)
        self.assertIsNone(self.usuarios.invalidar_sesiones(999999))

    def test_error_al_revocar_revierte_cambio_de_credencial_y_version(self):
        self.crear_sesion()

        def fallar(conexion, cursor, sentencia, parametros, contexto, muchos):
            if sentencia.startswith("UPDATE sesiones"):
                raise RuntimeError("Fallo de persistencia simulado")

        event.listen(self.engine, "before_cursor_execute", fallar)
        try:
            with self.assertRaises(RuntimeError):
                self.usuarios.cambiar_password_hash(self.usuario.id, HASH_CREDENCIAL + "nuevo")
        finally:
            event.remove(self.engine, "before_cursor_execute", fallar)
        self.assertEqual(self.usuarios.buscar_por_id(self.usuario.id), self.usuario)
        self.assertIsNone(self.sesiones.buscar_por_hash("a" * 64).revocada_en)

    def test_bd_rechaza_roles_y_versiones_invalidas(self):
        for cambios in ({"rol": "invitado"}, {"version_tokens": -1}, {"email": "MAYUSCULA@example.com"}):
            with self.subTest(cambios=cambios), self.assertRaises(IntegrityError):
                with self.factory.begin() as session:
                    session.add(UsuarioModel(**{
                        "email": "nuevo@example.com", "password_hash": HASH_CREDENCIAL, **cambios,
                    }))

    def test_rechaza_token_sin_hash_y_fechas_invalidas(self):
        futuro = datetime.now(timezone.utc) + timedelta(days=1)
        for valor in ("token-en-claro", "g" * 64, ""):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                self.sesiones.crear(self.usuario.id, valor, futuro, 0)
        for fecha in (futuro.replace(tzinfo=None), futuro - timedelta(days=2)):
            with self.assertRaises(ValueError):
                self.sesiones.crear(self.usuario.id, "a" * 64, fecha, 0)


class TestMigracionUsuariosSesiones(BaseUsuariosSesiones):
    @classmethod
    def preparar(cls):
        cls.alembic("upgrade", "0001")
        with cls.engine.begin() as conexion:
            for numero in range(1, 26):
                conexion.execute(ClienteModel.__table__.insert().values(
                    id=numero, nombre="Cliente", apellido="Prueba", telefono="+56912345678",
                    email=f"cliente{numero}@example.com", direccion="Calle Prueba 123",
                ))
                conexion.execute(VehiculoModel.__table__.insert().values(
                    id=numero, cliente_id=numero, patente=f"AA{numero:04}", marca="Toyota",
                    modelo="Yaris", anio=2020, kilometraje=1000,
                ))
                conexion.execute(OrdenTrabajoModel.__table__.insert().values(
                    id=numero, vehiculo_id=numero, fecha_ingreso=date(2026, 1, 1),
                    descripcion_problema="Revisión de frenos", kilometraje_ingreso=1000, estado="pendiente",
                ))
                conexion.execute(ReparacionModel.__table__.insert().values(
                    id=numero, orden_trabajo_id=numero, descripcion="Revisión", tipo="diagnostico",
                    costo=15000, fecha=date(2026, 1, 1),
                ))

    def test_upgrade_y_downgrade_conservan_datos_del_taller(self):
        self.alembic("upgrade", "head")
        self.assertIn("No new upgrade operations", self.alembic("check"))
        tablas = (ClienteModel, VehiculoModel, OrdenTrabajoModel, ReparacionModel)

        def verificar():
            with self.engine.connect() as conexion:
                for modelo in tablas:
                    self.assertEqual(conexion.scalar(select(func.count()).select_from(modelo)), 25)
                self.assertEqual(conexion.scalar(select(ClienteModel.email).where(ClienteModel.id == 1)),
                                 "cliente1@example.com")

        verificar()
        self.alembic("downgrade", "0001")
        self.assertNotIn("usuarios", inspect(self.engine).get_table_names())
        verificar()
        self.alembic("upgrade", "head")
        verificar()
