"""Comprueba la sustitución de servicios en la frontera HTTP sin usar la BD."""

import json
import unittest
from unittest.mock import Mock

from proyectobackend.main import app
from proyectobackend.routers.dependencies import (
    get_cliente_service,
    get_orden_trabajo_service,
    get_reparacion_service,
    get_vehiculo_service,
)


class TestDependenciasRouters(unittest.IsolatedAsyncioTestCase):
    async def solicitar_get(self, ruta):
        mensajes = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(mensaje):
            mensajes.append(mensaje)

        await app(
            {
                "type": "http", "asgi": {"version": "3.0"},
                "http_version": "1.1", "method": "GET", "scheme": "http",
                "path": ruta, "raw_path": ruta.encode(), "root_path": "",
                "query_string": b"", "headers": [],
                "client": ("127.0.0.1", 1234), "server": ("pruebas", 80),
            },
            receive,
            send,
        )
        estado = next(m["status"] for m in mensajes if m["type"] == "http.response.start")
        cuerpo = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
        return estado, json.loads(cuerpo)

    async def test_los_cuatro_routers_permiten_sustituir_su_servicio(self):
        pagina = {"items": [], "total": 0, "pagina": 1, "limite": 10, "total_paginas": 0}
        casos = (
            ("/clientes", get_cliente_service, "listar", pagina),
            ("/vehiculos/", get_vehiculo_service, "listar_vehiculos", []),
            ("/ordenes-trabajo", get_orden_trabajo_service, "listar", pagina),
            ("/reparaciones/", get_reparacion_service, "listar_reparaciones", []),
        )
        originales = app.dependency_overrides.copy()
        try:
            for ruta, proveedor, metodo, esperado in casos:
                with self.subTest(ruta=ruta):
                    servicio = Mock()
                    getattr(servicio, metodo).return_value = esperado
                    app.dependency_overrides[proveedor] = lambda: servicio
                    estado, cuerpo = await self.solicitar_get(ruta)
                    self.assertEqual(estado, 200)
                    self.assertEqual(cuerpo, esperado)
                    getattr(servicio, metodo).assert_called_once()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(originales)

    async def test_openapi_documenta_negocio_sin_exponer_servicios(self):
        documento = app.openapi()
        operaciones = []
        for ruta, metodos in documento["paths"].items():
            if ruta == "/":
                continue
            for metodo, operacion in metodos.items():
                with self.subTest(ruta=ruta, metodo=metodo):
                    self.assertTrue(operacion.get("summary"))
                    self.assertTrue(operacion.get("description"))
                    parametros = {p["name"] for p in operacion.get("parameters", [])}
                    self.assertTrue(parametros.isdisjoint({"service", "vehiculo_service"}))
                    operaciones.append((ruta, metodo))
        self.assertEqual(len(operaciones), 19)
