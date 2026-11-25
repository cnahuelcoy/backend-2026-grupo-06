from datetime import date
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, delete, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from proyectobackend.database.base import Base
from proyectobackend.database.session import configurar_minusculas_sqlite
from proyectobackend.domain.orden_trabajo import EstadoOrdenTrabajo
from proyectobackend.models.cliente import ClienteModel
from proyectobackend.models.orden_trabajo import OrdenTrabajoModel
from proyectobackend.models.vehiculo import VehiculoModel
from proyectobackend.repositories.cliente_repository import ClienteRepository
from proyectobackend.repositories.orden_trabajo_repositorio import (
    OrdenTrabajoRepository,
)
from proyectobackend.services.cliente_service import ClienteService
from proyectobackend.services.orden_trabajo_services import OrdenTrabajoService


class TestPaginacionSQL(unittest.TestCase):
    def setUp(self):
        temporal = TemporaryDirectory(prefix="paginacion-sql-")
        self.addCleanup(temporal.cleanup)
        url = os.getenv("TEST_PAGINACION_POSTGRES_URL")
        if url:
            if make_url(url).get_backend_name() != "postgresql":
                raise ValueError("TEST_PAGINACION_POSTGRES_URL debe usar PostgreSQL")
            esquema = "test_paginacion_" + uuid4().hex
            self.engine = create_engine(
                url,
                execution_options={"schema_translate_map": {None: esquema}},
            )
            self.addCleanup(self.engine.dispose)
            with self.engine.begin() as conexion:
                conexion.execute(CreateSchema(esquema))

            def limpiar():
                with self.engine.begin() as conexion:
                    conexion.execute(DropSchema(esquema, cascade=True))

            self.addCleanup(limpiar)
        else:
            self.engine = create_engine(
                "sqlite:///" + str(Path(temporal.name) / "datos.db")
            )
            self.addCleanup(self.engine.dispose)
            event.listen(self.engine, "connect", configurar_minusculas_sqlite)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        for modulo in ("cliente_repository", "orden_trabajo_repositorio"):
            parche = patch(
                "proyectobackend.repositories." + modulo + ".SessionLocal",
                self.sessions,
            )
            parche.start()
            self.addCleanup(parche.stop)
        self.clientes = ClienteRepository()
        self.ordenes = OrdenTrabajoRepository()
        self.servicio_clientes = ClienteService(self.clientes)
        self.servicio_ordenes = OrdenTrabajoService(self.ordenes, None)
        self.datos_clientes = [
            dict(
                id=i,
                nombre=nombre,
                apellido=apellido,
                email=f"cliente{i:02}@example.com",
                telefono="+56912345678",
                direccion="Calle Pruebas 123",
            )
            for i, (nombre, apellido) in enumerate(
                [
                    ("Ana", "Perez"),
                    ("ana", "Lopez"),
                    ("Ana", "Lopez"),
                    ("Beto", "Perez"),
                    ("Álvaro", "Diaz"),
                    ("álvaro", "Diaz"),
                    ("Anna", "Soto"),
                    ("A%_", "Soto"),
                    ("Ana", "Lopez"),
                ],
                1,
            )
        ]
        estados = list(EstadoOrdenTrabajo)
        self.datos_ordenes = [
            dict(
                id=i,
                vehiculo_id=1,
                fecha_ingreso=date(2026, 1, 1 + i % 3),
                descripcion_problema="Revisar frenos",
                kilometraje_ingreso=(i % 2) * 1000,
                estado=estados[i % 3],
            )
            for i in range(1, 13)
        ]
        with self.sessions.begin() as session:
            session.add_all(ClienteModel(**dato) for dato in self.datos_clientes)
            session.flush()
            session.add(
                VehiculoModel(
                    id=1,
                    cliente_id=1,
                    patente="TEST01",
                    marca="Toyota",
                    modelo="Yaris",
                    anio=2020,
                    kilometraje=1000,
                )
            )
            session.flush()
            session.add_all(OrdenTrabajoModel(**dato) for dato in self.datos_ordenes)

    def comprobar_pagina(self, respuesta, datos, columna, direccion, pagina, limite):
        esperados = sorted(
            datos, key=lambda dato: dato[columna], reverse=direccion == "desc"
        )
        self.assertEqual(respuesta["total"], len(datos))
        self.assertEqual(
            respuesta["total_paginas"], (len(datos) + limite - 1) // limite
        )
        self.assertEqual(respuesta["pagina"], pagina)
        self.assertEqual(respuesta["limite"], limite)
        inicio = (pagina - 1) * limite
        items = respuesta["items"]
        ids = [item["id"] if isinstance(item, dict) else item.id for item in items]
        self.assertEqual(
            ids, [dato["id"] for dato in esperados[inicio : inicio + limite]]
        )

    def test_clientes_conservan_filtros_orden_y_metadatos(self):
        for nombre in (None, "ANA", "ÁLVARO", "A%_", "No existe"):
            datos = [
                d
                for d in self.datos_clientes
                if nombre is None or d["nombre"].lower() == nombre.lower()
            ]
            for columna in ("id", "nombre", "apellido", "email"):
                for direccion in ("asc", "desc"):
                    for pagina in (1, 2, 3, 20):
                        with self.subTest(
                            nombre=nombre,
                            columna=columna,
                            direccion=direccion,
                            pagina=pagina,
                        ):
                            respuesta = self.servicio_clientes.listar(
                                nombre, columna, direccion, pagina, 2
                            )
                            self.comprobar_pagina(
                                respuesta, datos, columna, direccion, pagina, 2
                            )

    def test_ordenes_conservan_filtros_orden_y_metadatos(self):
        for estado in (None, *EstadoOrdenTrabajo):
            datos = [
                d for d in self.datos_ordenes if estado is None or d["estado"] == estado
            ]
            for columna in ("id", "fecha_ingreso", "kilometraje_ingreso"):
                for direccion in ("asc", "desc"):
                    for pagina in (1, 2, 3, 20):
                        with self.subTest(
                            estado=estado,
                            columna=columna,
                            direccion=direccion,
                            pagina=pagina,
                        ):
                            respuesta = self.servicio_ordenes.listar(
                                estado, columna, direccion, pagina, 2
                            )
                            self.comprobar_pagina(
                                respuesta.model_dump(),
                                datos,
                                columna,
                                direccion,
                                pagina,
                                2,
                            )

    def test_sin_resultados_y_limite_maximo(self):
        with self.sessions.begin() as session:
            session.execute(delete(OrdenTrabajoModel))
        respuesta = self.servicio_ordenes.listar(pagina=2, limite=100)
        self.comprobar_pagina(respuesta.model_dump(), [], "id", "asc", 2, 100)
        respuesta = self.servicio_clientes.listar(limite=100)
        self.comprobar_pagina(respuesta, self.datos_clientes, "id", "asc", 1, 100)

    def test_empates_no_repiten_ni_omiten_registros_entre_paginas(self):
        for servicio, parametros, total in (
            (
                self.servicio_clientes,
                {"ordenar_por": "apellido", "direccion": "desc"},
                9,
            ),
            (
                self.servicio_ordenes,
                {"ordenar_por": "kilometraje_ingreso", "direccion": "desc"},
                12,
            ),
        ):
            ids = []
            for pagina in range(1, (total + 1) // 2 + 1):
                respuesta = servicio.listar(**parametros, pagina=pagina, limite=2)
                items = (
                    respuesta["items"]
                    if isinstance(respuesta, dict)
                    else respuesta.items
                )
                ids.extend(item.id for item in items)
            self.assertEqual(len(ids), total)
            self.assertEqual(len(set(ids)), total)

    def test_sql_filtra_cuenta_y_materializa_solo_la_pagina(self):
        for repo, parametros in (
            (self.clientes, {"nombre": "ANA"}),
            (self.ordenes, {"estado": EstadoOrdenTrabajo.PENDIENTE}),
        ):
            consultas = []

            def capturar(conexion, cursor, statement, valores, contexto, muchos):
                consultas.append(statement.upper())

            event.listen(self.engine, "before_cursor_execute", capturar)
            try:
                with patch.object(
                    repo, "_to_domain", wraps=repo._to_domain
                ) as convertir:
                    items, total = repo.listar_paginado(
                        **parametros, pagina=2, limite=1
                    )
                    self.assertEqual(len(items), 1)
                    self.assertEqual(convertir.call_count, 1)
                    self.assertEqual(total, 4)
            finally:
                event.remove(self.engine, "before_cursor_execute", capturar)
            self.assertEqual(len(consultas), 2)
            self.assertIn("COUNT(", consultas[0])
            for parte in ("WHERE", "ORDER BY", "LIMIT", "OFFSET"):
                self.assertIn(parte, consultas[1])

    def test_repositorios_rechazan_columnas_y_paginacion_invalidas(self):
        for repo in (self.clientes, self.ordenes):
            for parametros in (
                {"ordenar_por": "id; DROP TABLE clientes"},
                {"direccion": "invalid"},
                {"pagina": 0},
                {"limite": 101},
            ):
                with self.subTest(repo=type(repo).__name__, parametros=parametros):
                    with self.assertRaises(ValueError):
                        repo.listar_paginado(**parametros)
