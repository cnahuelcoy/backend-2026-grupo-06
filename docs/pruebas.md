# Pruebas de la API

La suite incluye **74 pruebas** de negocio, persistencia y base de autenticación.
El 24 de noviembre pasaron las 74 con Docker habilitado y las 14 nuevas también
en PostgreSQL aislado. Los esquemas y contenedores de prueba se eliminaron.

## Ejecutar

Desde la raíz del proyecto:

```powershell
uv sync --frozen
uv run --no-sync python -B -W error::ResourceWarning -m unittest discover -s tests -t . -v
```

## Casos comprobados

| Archivo en tests/ | Pruebas | Qué revisa |
|---|---:|---|
| test_clientes.py | 6 | Altas, consultas, cambios y validación de clientes. |
| test_integracion.py | 3 | Relaciones, paginación y persistencia al reiniciar la API. |
| test_revision_final.py | 33 | Errores HTTP, validaciones, eliminaciones y reglas de negocio. |
| test_dependencias_routers.py | 2 | Sustitución de los cuatro servicios y documentación OpenAPI. |
| test_concurrencia_ordenes.py | 8 | Cambios simultáneos, actualizaciones sucesivas, orden finalizada, eliminación, escritura parcial y PATCH vacío o null. |
| test_reconexion_bd.py | 2 | Conexión cerrada y primera consulta tras dos reinicios de PostgreSQL, sin reiniciar la API. |
| test_paginacion_sql.py | 6 | Filtros, orden, desempates por ID, límites, páginas vacías, totales y consultas SQL. |
| test_usuarios_sesiones.py | 14 | Migración, unicidad, DTO, roles, consumo simultáneo, revocación y rollback. |

La suite usa SQLite temporal o servicios sustituidos. No modifica las tablas
del taller. También comprueba errores JSON y respuestas 204 sin cuerpo.
Órdenes no tiene endpoint DELETE; se comprueban los métodos que sí implementa.

Usuarios/sesiones también se verifica con "TEST_USUARIOS_POSTGRES_URL" apuntando
a una BD de prueba: `uv run --no-sync python -m unittest tests.test_usuarios_sesiones -v`.
Crea esquemas aislados, aplica Alembic y los elimina al terminar. La migración
se prueba desde cero y desde "0001" con 25 registros por tabla del taller.

La reconexión usa "pool_pre_ping" para descartar conexiones cerradas al
reutilizarlas. La prueba Docker usa contenedores y una red temporales, sin
reiniciar la base del taller. Requiere las imágenes "postgres:17-alpine" y
"proyectobackend-backend"; sin la variable indicada se omite ese caso:

```powershell
$env:TEST_RECONEXION_DOCKER = "1"
uv run --no-sync python -m unittest tests.test_reconexion_bd -v
Remove-Item Env:TEST_RECONEXION_DOCKER
```

## Actualizaciones simultáneas de órdenes

Antes, dos PATCH podían sobrescribirse. Ahora el UPDATE escribe solo los campos
enviados y comprueba que la orden no haya cambiado desde su lectura. Si cambió,
responde 409 con "WORK_ORDER_CONCURRENT_UPDATE"; hay que consultar la orden
antes de reenviar el cambio. Si fue eliminada, responde 404. No requiere migración.
La protección cubre solicitudes simultáneas; no detecta formularios antiguos
que se envían después de que terminó otra actualización.
Un PATCH vacío o con solo valores null no ejecuta un UPDATE.

Los ocho casos pasaron también en PostgreSQL 17.11, usando esquemas temporales
separados. No quedaron esquemas de prueba y se conservaron los 25 registros
por tabla del taller.

Para repetirlos, definir "TEST_ORDENES_POSTGRES_URL" con una URL
"postgresql+psycopg://usuario:clave@host:puerto/base" de pruebas y ejecutar:

```powershell
uv run --no-sync python -m unittest tests.test_concurrencia_ordenes -v
```

Cada caso crea y elimina su esquema "test_ordenes_<uuid>"; no usa las tablas
de "public". La conexión necesita permiso para crear esos esquemas.

## Comprobaciones anteriores

El [PR #36](https://github.com/cnahuelcoy/backend-2026-grupo-06/pull/36) corrigió
el error 500 al eliminar vehículos con órdenes: ahora responde 409 con
"VEHICLE_HAS_WORK_ORDERS" y conserva los registros relacionados.
También se corrigieron los bloqueos de archivos temporales en
"tests/soporte_api.py". Sus pruebas siguen en la suite.

El archivo [solicitudes.http](solicitudes.http) contiene 60 solicitudes para
REST Client. Salinas informó que pasaron; no se repitió esa secuencia manual
en esta revisión. Las instrucciones están en el
[README](../README.md#pruebas-http-con-rest-client). Usar la API temporal,
porque esas solicitudes crean, modifican y eliminan registros.

Las seis pruebas de paginación pasaron también en PostgreSQL 17.11.
Comprueban respuestas equivalentes, totales, orden estable y lectura solo de la página.
Usan esquemas temporales que se eliminan al terminar. Para repetirlas, definir
"TEST_PAGINACION_POSTGRES_URL" y ejecutar:

```powershell
uv run --no-sync python -m unittest tests.test_paginacion_sql -v
```
