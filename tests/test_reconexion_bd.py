import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from sqlalchemy.engine import URL


class TestReconexionBD(unittest.TestCase):
    def test_primera_consulta_recupera_una_conexion_cerrada(self):
        script = """
from sqlalchemy import text
from proyectobackend.database.session import engine
with engine.begin() as conn:
    conn.execute(text("CREATE TABLE comprobacion (id INTEGER PRIMARY KEY)"))
    conn.execute(text("INSERT INTO comprobacion VALUES (1)"))
connection = engine.raw_connection()
driver = connection.driver_connection
connection.close()
driver.close()
with engine.connect() as conn:
    assert conn.execute(text("SELECT id FROM comprobacion")).scalar_one() == 1
engine.dispose()
"""
        with TemporaryDirectory(prefix="reconexion-sqlite-") as tmp:
            env = os.environ.copy()
            env["DATABASE_URL"] = "sqlite:///" + str(Path(tmp) / "prueba.db")
            resultado = subprocess.run(
                [sys.executable, "-B", "-c", script], env=env,
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(resultado.returncode, 0, resultado.stderr)

    @unittest.skipUnless(os.getenv("TEST_RECONEXION_DOCKER") == "1",
                         "Definir TEST_RECONEXION_DOCKER=1 para reiniciar un PostgreSQL aislado")
    def test_primera_peticion_tras_dos_reinicios_postgresql(self):
        nombre = "test-reconexion-" + uuid4().hex
        api_nombre = nombre + "-api"
        clave = secrets.token_hex(16)

        def docker(*args):
            return subprocess.run(
                ["docker", *args], check=True, capture_output=True, text=True, timeout=90,
            ).stdout.strip()

        docker("network", "create", nombre)
        self.addCleanup(lambda: docker("network", "rm", nombre))
        docker("run", "-d", "--name", nombre, "--network", nombre,
               "--network-alias", "db",
               "-e", "POSTGRES_USER=taller_test", "-e", "POSTGRES_DB=reconexion_test",
               "-e", "POSTGRES_PASSWORD=" + clave,
               "--health-cmd", "pg_isready -h 127.0.0.1 -U taller_test -d reconexion_test",
               "--health-interval", "1s", "--health-timeout", "2s", "--health-retries", "30",
               "postgres:17-alpine")
        self.addCleanup(lambda: docker("rm", "-f", "-v", nombre))

        def esperar_bd():
            limite = time.monotonic() + 60
            while time.monotonic() < limite:
                if docker("inspect", "--format", "{{.State.Health.Status}}", nombre) == "healthy":
                    return
                time.sleep(0.25)
            self.fail("El PostgreSQL aislado no volvió a estar saludable")

        esperar_bd()
        database_url = URL.create(
            "postgresql+psycopg", username="taller_test", password=clave,
            host="db", port=5432, database="reconexion_test",
        ).render_as_string(hide_password=False)
        src = Path(__file__).resolve().parents[1] / "src"
        docker("run", "-d", "--name", api_nombre, "--network", nombre,
               "-e", "DATABASE_URL=" + database_url,
               "-e", "JWT_SECRET_KEY=" + secrets.token_urlsafe(48),
               "--mount", f"type=bind,source={src},target=/app/src,readonly",
               "-p", "127.0.0.1::8000", "proyectobackend-backend")
        self.addCleanup(lambda: docker("rm", "-f", api_nombre))
        puerto_api = int(docker("port", api_nombre, "8000/tcp").rsplit(":", 1)[1])
        url = f"http://127.0.0.1:{puerto_api}"
        http = build_opener(ProxyHandler({}))

        access = None

        def solicitar(ruta, datos=None):
            contenido = json.dumps(datos).encode() if datos is not None else None
            peticion = Request(
                url + ruta, data=contenido,
                headers={"Content-Type": "application/json", **(
                    {"Authorization": "Bearer " + access} if access else {}
                )},
            )
            try:
                respuesta = http.open(peticion, timeout=10)
            except HTTPError as error:
                respuesta = error
            with respuesta:
                return respuesta.status, json.loads(respuesta.read())

        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            self.assertEqual(docker("inspect", "--format", "{{.State.Running}}", api_nombre), "true")
            try:
                if solicitar("/")[0] == 200:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        else:
            self.fail("La API aislada no quedó disponible: " + docker("logs", api_nombre))

        pid_api = docker("inspect", "--format", "{{.State.Pid}}", api_nombre)
        credenciales = {"email": "reconexion@example.com", "password": secrets.token_urlsafe(24)}
        self.assertEqual(solicitar("/auth/registro", credenciales)[0], 201)
        estado, identidad = solicitar("/auth/login", credenciales)
        self.assertEqual(estado, 200)
        access = identidad["access_token"]
        estado, _ = solicitar("/clientes", {
            "nombre": "Ana", "apellido": "Pruebas", "telefono": "+56912345678",
            "email": "reconexion@example.com", "direccion": "Calle Pruebas 123",
        })
        self.assertEqual(estado, 201)
        estado, esperado = solicitar("/clientes")
        self.assertEqual(estado, 200)
        self.assertEqual(esperado["total"], 1)
        for intento in range(2):
            with self.subTest(reinicio=intento + 1):
                docker("restart", nombre)
                esperar_bd()
                self.assertEqual(docker("inspect", "--format", "{{.State.Pid}}", api_nombre), pid_api)
                estado, datos = solicitar("/clientes")
                self.assertEqual(estado, 200, datos)
                self.assertEqual(datos, esperado)
