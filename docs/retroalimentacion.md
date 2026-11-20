# Seguimiento de la retroalimentación

Revisión del 20 de noviembre de 2026. Correcciones en el commit `381d053`
de la rama `cnahuelcoy`.

| ID | Observación | Cambio y evidencia | Estado |
|---|---|---|---|
| R01 | Usar PostgreSQL | API conectada a PostgreSQL 17.11 mediante `DATABASE_URL` en `compose.yaml`. | Verificado |
| R02 | Base de datos en contenedor | Servicio `db` saludable y volumen persistente `postgres_data`. | Verificado |
| R03 | Demostrar dónde están los datos | Base `taller_mecanico`: consultas desde el contenedor, Windows y la API coinciden, con 25 registros por tabla. | Verificado |
| R04 | «El string es demasiado corto» | La observación no identifica el campo ni la longitud requerida. | Pendiente de aclaración |
| R05 | Publicar el puerto de la base | PostgreSQL en `127.0.0.1:15432:5432`; API y Swagger en `8000:8000`. Conexión documentada en el README. | Verificado |
| R06 | Separar las rutas | Cuatro routers y proveedores comunes en `routers/dependencies.py`, con inyección mediante `Depends`. | Implementado y probado |
| R07 | Completar OpenAPI | Se añadieron los resúmenes y descripciones ausentes en Vehículos y Órdenes y las descripciones faltantes en Clientes. Las 19 operaciones quedan documentadas. | Verificado |

## Evidencia de verificación

- **44 pruebas aprobadas**, con SQLite temporal o servicios sustituidos; incluye
  `tests/test_dependencias_routers.py`.
- Contrato OpenAPI conservado, salvo los resúmenes y descripciones agregados.
- Imagen Docker reconstruida; los cuatro listados y Swagger responden `200`.
- **25 clientes, 25 vehículos, 25 órdenes y 25 reparaciones**: todos sus campos
  coinciden entre PostgreSQL externo y la API. Comprobación de solo lectura.
- Alembic en `0001 (head)`, sin diferencias de esquema; datos conservados al
  reconstruir la API. No se ensayó un reinicio de PostgreSQL.
- Conexión externa comprobada desde Windows por `15432`; no se verificó la
  interfaz de VS Code. El puerto `5432` está ocupado por otro proyecto.

Para repetir la suite: `uv run --no-sync python -m unittest discover -v`.
Conexión y arranque: [README](../README.md#instalación-y-ejecución-con-docker).
