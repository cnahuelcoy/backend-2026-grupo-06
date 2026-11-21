import asyncio
from datetime import date
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.engine import make_url

from proyectobackend.database.base import Base
from proyectobackend.domain.orden_trabajo import EstadoOrdenTrabajo
from proyectobackend.models.cliente import ClienteModel
from proyectobackend.models.orden_trabajo import OrdenTrabajoModel
from proyectobackend.models.vehiculo import VehiculoModel
from proyectobackend.repositories.orden_trabajo_repositorio import OrdenTrabajoRepository
from proyectobackend.routers.dependencies import get_orden_trabajo_service
from proyectobackend.routers.orden_trabajo_routers import router
from proyectobackend.services.orden_trabajo_services import OrdenTrabajoService


class TestConcurrenciaOrdenes(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporal = TemporaryDirectory(prefix="concurrencia-ordenes-")
        self.addCleanup(temporal.cleanup)
        postgres_url = os.getenv("TEST_ORDENES_POSTGRES_URL")
        if postgres_url:
            if make_url(postgres_url).get_backend_name() != "postgresql":
                raise ValueError("TEST_ORDENES_POSTGRES_URL debe usar PostgreSQL")
            # Todos los modelos se traducen a un esquema exclusivo por prueba;
            # nunca se crean, modifican ni borran tablas del esquema public.
            esquema = "test_ordenes_" + uuid4().hex
            engine = create_engine(
                postgres_url,
                execution_options={"schema_translate_map": {None: esquema}},
            )
            self.addCleanup(engine.dispose)
            with engine.begin() as conexion:
                conexion.execute(CreateSchema(esquema))

            def limpiar_esquema():
                with engine.begin() as conexion:
                    conexion.execute(DropSchema(esquema, cascade=True))

            self.addCleanup(limpiar_esquema)
        else:
            engine = create_engine(
                "sqlite:///" + str(Path(temporal.name) / "ordenes.db"),
                connect_args={"check_same_thread": False},
            )
            self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.sessions = sessionmaker(bind=engine, expire_on_commit=False)
        parche = patch(
            "proyectobackend.repositories.orden_trabajo_repositorio.SessionLocal",
            self.sessions,
        )
        parche.start()
        self.addCleanup(parche.stop)
        with self.sessions.begin() as session:
            session.add(ClienteModel(
                id=1, nombre="Ana", apellido="Perez", telefono="+56912345678",
                email="ana@example.com", direccion="Calle Pruebas 123",
            ))
            session.flush()
            session.add(VehiculoModel(
                id=1, cliente_id=1, patente="TEST01", marca="Toyota",
                modelo="Yaris", anio=2020, kilometraje=1000,
            ))
            session.flush()
            session.add(OrdenTrabajoModel(
                id=1, vehiculo_id=1, fecha_ingreso=date(2026, 1, 10),
                descripcion_problema="Revisar frenos", kilometraje_ingreso=1000,
                estado=EstadoOrdenTrabajo.PENDIENTE,
            ))
        self.repo = OrdenTrabajoRepository()
        self.service = OrdenTrabajoService(self.repo, Mock())
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_orden_trabajo_service] = lambda: self.service

    async def actualizar(self, cambios, orden_id=1):
        mensajes = []
        cuerpo = json.dumps(cambios).encode()
        ruta = f"/ordenes-trabajo/{orden_id}"

        async def receive():
            return {"type": "http.request", "body": cuerpo, "more_body": False}

        async def send(mensaje):
            mensajes.append(mensaje)

        await self.app({
            "type": "http", "asgi": {"version": "3.0"},
            "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": ruta, "raw_path": ruta.encode(), "root_path": "",
            "query_string": b"", "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 1234), "server": ("pruebas", 80),
        }, receive, send)
        estado = next(m["status"] for m in mensajes if m["type"] == "http.response.start")
        datos = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
        return estado, json.loads(datos)

    async def test_dos_patch_con_la_misma_lectura_no_sobrescriben_cambios(self):
        await self.comprobar_conflicto([
            {"estado": "finalizada", "descripcion_problema": "Trabajo terminado"},
            {"estado": "en_reparacion", "kilometraje_ingreso": 2000},
        ])

    async def test_dos_patch_de_campos_distintos_tambien_detectan_conflicto(self):
        await self.comprobar_conflicto([
            {"descripcion_problema": "Revisar motor"},
            {"kilometraje_ingreso": 2000},
        ])

    async def comprobar_conflicto(self, cambios):
        barrera = Barrier(2, timeout=10)
        buscar = self.repo.buscar_por_id

        def leer_antes_de_actualizar(orden_id):
            orden = buscar(orden_id)
            barrera.wait()
            return orden

        with patch.object(self.repo, "buscar_por_id", leer_antes_de_actualizar):
            resultados = await asyncio.gather(*(self.actualizar(c) for c in cambios))
        self.assertEqual(sorted(estado for estado, _ in resultados), [200, 409])
        ganador = next(i for i, (estado, _) in enumerate(resultados) if estado == 200)
        conflicto = resultados[1 - ganador][1]
        self.assertEqual(conflicto["error"]["code"], "WORK_ORDER_CONCURRENT_UPDATE")
        guardada = self.repo.buscar_por_id(1)
        self.assertEqual(guardada.estado.value, cambios[ganador].get("estado", "pendiente"))
        self.assertEqual(guardada.descripcion_problema,
                         cambios[ganador].get("descripcion_problema", "Revisar frenos"))
        self.assertEqual(guardada.kilometraje_ingreso,
                         cambios[ganador].get("kilometraje_ingreso", 1000))

    async def test_patch_sucesivos_conservan_los_campos_anteriores(self):
        self.assertEqual((await self.actualizar({"descripcion_problema": "Revisar motor"}))[0], 200)
        estado, cuerpo = await self.actualizar({"kilometraje_ingreso": 2500})
        self.assertEqual(estado, 200)
        self.assertEqual(cuerpo["descripcion_problema"], "Revisar motor")
        self.assertEqual(cuerpo["kilometraje_ingreso"], 2500)

    async def test_finalizada_no_se_reabre_ni_guarda_otros_campos(self):
        self.assertEqual((await self.actualizar({"estado": "finalizada"}))[0], 200)
        estado, cuerpo = await self.actualizar({"estado": "pendiente", "kilometraje_ingreso": 3000})
        self.assertEqual(estado, 409)
        self.assertEqual(cuerpo["error"]["code"], "INVALID_WORK_ORDER_STATE")
        orden = self.repo.buscar_por_id(1)
        self.assertEqual(orden.estado, EstadoOrdenTrabajo.FINALIZADA)
        self.assertEqual(orden.kilometraje_ingreso, 1000)

    async def test_orden_eliminada_entre_lectura_y_guardado_devuelve_404(self):
        buscar = self.repo.buscar_por_id

        def leer_y_eliminar(orden_id):
            orden = buscar(orden_id)
            with self.sessions.begin() as session:
                session.delete(session.get(OrdenTrabajoModel, orden_id))
            return orden

        with patch.object(self.repo, "buscar_por_id", leer_y_eliminar):
            estado, cuerpo = await self.actualizar({"kilometraje_ingreso": 3000})
        self.assertEqual(estado, 404)
        self.assertEqual(cuerpo["error"]["code"], "WORK_ORDER_NOT_FOUND")

    async def test_patch_sin_cambios_conserva_la_orden(self):
        estado, cuerpo = await self.actualizar({})
        self.assertEqual(estado, 200)
        self.assertEqual(cuerpo["estado"], "pendiente")
        self.assertEqual(cuerpo["kilometraje_ingreso"], 1000)

    async def test_sql_actualiza_solo_el_campo_enviado(self):
        sentencias = []
        engine = self.sessions.kw["bind"]

        def capturar(conexion, cursor, statement, parametros, contexto, muchos):
            if statement.lstrip().upper().startswith("UPDATE "):
                sentencias.append(statement)

        event.listen(engine, "before_cursor_execute", capturar)
        try:
            estado, cuerpo = await self.actualizar({"kilometraje_ingreso": 2300})
        finally:
            event.remove(engine, "before_cursor_execute", capturar)
        self.assertEqual(estado, 200)
        self.assertEqual(cuerpo["kilometraje_ingreso"], 2300)
        self.assertEqual(cuerpo["descripcion_problema"], "Revisar frenos")
        self.assertEqual(len(sentencias), 1)
        asignaciones = sentencias[0].split(" SET ", 1)[1].split(" WHERE ", 1)[0]
        columnas = [a.split("=", 1)[0].strip().strip("\"")
                    for a in asignaciones.split(",")]
        self.assertEqual(columnas, ["kilometraje_ingreso"])

    async def test_patch_vacio_o_null_no_ejecuta_update(self):
        sentencias = []
        engine = self.sessions.kw["bind"]

        def capturar(conexion, cursor, statement, parametros, contexto, muchos):
            if statement.lstrip().upper().startswith("UPDATE "):
                sentencias.append(statement)

        event.listen(engine, "before_cursor_execute", capturar)
        try:
            for datos in ({}, {"estado": None, "kilometraje_ingreso": None}):
                with self.subTest(datos=datos):
                    estado, cuerpo = await self.actualizar(datos)
                    self.assertEqual(estado, 200)
                    self.assertEqual(cuerpo["estado"], "pendiente")
                    self.assertEqual(cuerpo["kilometraje_ingreso"], 1000)
        finally:
            event.remove(engine, "before_cursor_execute", capturar)
        self.assertEqual(sentencias, [])
