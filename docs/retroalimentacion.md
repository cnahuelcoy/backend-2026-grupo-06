# Seguimiento de la retroalimentación

Revisión local del 20 de noviembre de 2026 sobre la rama `cnahuelcoy`, con base
`07a1bed`. Esta revisión atiende las imágenes entregadas por Carlos y su tarjeta
de unificación de dependencias. No incorpora autenticación ni otros requisitos
nuevos de la entrega final. Los cambios siguen sin commit ni PR.

## Observaciones recibidas

| ID | Observación | Cambio o evidencia en el proyecto | Estado de esta revisión |
|---|---|---|---|
| R01 | Migrar SQLite a PostgreSQL | `compose.yaml` configura `postgres:17-alpine` y `DATABASE_URL` de la API con `postgresql+psycopg` y host `db`. `migrations/versions/0001_esquema_inicial.py` contiene el esquema de cuatro tablas. SQLite se mantiene para desarrollo sin configuración y para pruebas aisladas. | Verificado: API en Docker conectada a PostgreSQL 17.11, base taller_mecanico; sus cuatro listados coinciden registro por registro con SQL desde Windows. No se ejecutó ni se necesita una nueva importación de SQLite para esta comprobación. |
| R02 | Tener la base en un contenedor | Servicio `db`, comprobación de salud y volumen `postgres_data` en `compose.yaml`. | Verificado: contenedor proyectobackend-db-1 saludable y volumen proyectobackend_postgres_data montado en /var/lib/postgresql/data. |
| R03 | Probar dónde están las bases de datos | Se añadió al README cómo identificar base, usuario, motor, registros y conteos desde el contenedor y un cliente PostgreSQL. Se explica la diferencia con `taller_mecanico.db`. | Verificado desde psql dentro del contenedor y una conexión PostgreSQL externa desde Windows: misma base, usuario y 25 filas por tabla. La configuración de la extensión concreta de VS Code queda a cargo del cliente; no se comprobó su interfaz. |
| R04 | «El string es demasiado corto» | La imagen no identifica campo, límite ni ejemplo rechazado. Las descripciones de órdenes y reparaciones usan `Text` en los modelos; otros campos tienen límites específicos. | Pendiente de precisar el campo y la longitud requerida. No se modificó una restricción por suposición. |
| R05 | Publicar un puerto externo para la base; revisar `8000:8000` | Se conserva el cambio local previo `127.0.0.1:15432:5432`. README documenta la conexión desde el equipo a `15432`, desde la API a `db:5432` y el puerto HTTP `8000`. | Verificado: conexión PostgreSQL externa por 127.0.0.1:15432; API y Swagger responden en 8000. El puerto 5432 de Windows pertenece a otro proyecto Docker. |
| R06 | Pasar a una estructura de routers | Ya existen cuatro routers incluidos en `main.py`. Se agregó `routers/dependencies.py` y se inyectan los cuatro servicios con `Depends`, sin reorganizar carpetas. | Implementado; prueba de sustitución HTTP en los cuatro módulos y suite de regresión. |
| R07 | Nueve endpoints de vehículos y órdenes sin resumen ni descripción en OpenAPI | Se agregaron `summary` y `description` a las nueve operaciones y descripciones que faltaban en Clientes. Reparaciones ya las incluía. | Las 19 operaciones de negocio tienen ambos campos; se preserva el contrato HTTP. |

## Responsabilidad de cada capa

`main.py` registra routers y manejadores. `routers/` convierte solicitudes y
respuestas HTTP; `routers/dependencies.py` compone servicios a partir de los
repositorios actuales. `services/` conserva la coordinación y reglas actuales;
`repositories/` conserva el acceso a SQLAlchemy y la gestión de sesiones.
`schemas/` valida los DTO y `models/` describe las tablas. No se agregaron
parámetros HTTP para los servicios ni lógica de persistencia a los routers.

Para sustituir un servicio en pruebas, usar como clave el proveedor de
`proyectobackend.routers.dependencies` en `app.dependency_overrides` y restaurar
los overrides al terminar. FastAPI resuelve el servicio por solicitud.

## Verificación reproducible

Desde la raíz del repositorio, con el entorno ya instalado:

```powershell
.venv\Scripts\python.exe -m unittest discover -v
```

`tests/test_dependencias_routers.py` sustituye los cuatro proveedores y envía
solicitudes HTTP ASGI, comprobando que se invoca el servicio sustituido. También
verifica que las 19 operaciones tengan resumen y descripción y que los servicios
no aparezcan como parámetros HTTP. Las pruebas existentes comprueban altas,
modificaciones, errores, relaciones y persistencia con SQLite temporal.

Se guardó y comparó OpenAPI antes y después del cambio: quitando exclusivamente
`summary` y `description`, ambos documentos son idénticos. No cambian rutas,
verbos, parámetros, cuerpos, esquemas ni respuestas declaradas.

La suite previa pasó con 42 pruebas. La suite ampliada pasó con **44 pruebas**
en 57,868 segundos el 20 de noviembre de 2026. Las 44 pruebas usan servicios
sustituidos o SQLite temporal. La comprobación posterior de PostgreSQL se hizo
con consultas de lectura: no insertó, modificó ni eliminó datos del taller.
`git diff --check` también terminó sin errores.

## Comprobación de Docker y PostgreSQL completada

El 20 de noviembre de 2026, después de iniciar Docker Desktop, se completó la
verificación que estaba pendiente por disponibilidad del motor:

- Docker Engine `29.9.1`; `docker compose config --quiet` sin errores.
- `docker compose build backend` terminó con las dependencias fijadas en
  `uv.lock`. Se reconstruyó la imagen con los cambios locales de `cnahuelcoy`.
- `docker compose up -d backend` inició la API y conservó el contenedor de
  PostgreSQL existente, sin borrar ni recrear su volumen.
- `docker compose ps`: API activa en `8000`; PostgreSQL saludable, publicado
  únicamente en `127.0.0.1:15432`, con su puerto interno `5432`.
- SQL dentro del contenedor identificó PostgreSQL `17.11`, base
  `taller_mecanico` y usuario `taller_app`.
- Una conexión Psycopg desde Windows a `127.0.0.1:15432` identificó esa misma
  base y usuario. La contraseña se leyó localmente de `.env` sin imprimirla.
- `alembic current` devolvió `0001 (head)` y `alembic check` devolvió
  `No new upgrade operations detected.` No fue necesario aplicar ni marcar
  migraciones sobre la base existente.
- El volumen `proyectobackend_postgres_data` está montado en
  `/var/lib/postgresql/data`. Los datos existentes se conservaron al reconstruir
  e iniciar la API. No se ensayó un reinicio del contenedor de PostgreSQL.

| Tabla | SQL en contenedor | SQL desde Windows | GET de la API |
|---|---:|---:|---:|
| clientes | 25 | 25 | 25 |
| vehiculos | 25 | 25 | 25 |
| ordenes_trabajo | 25 | 25 | 25 |
| reparaciones | 25 | 25 | 25 |

Además de los conteos, se compararon todos los campos de todos los registros de
los cuatro GET con `SELECT *` sobre PostgreSQL desde Windows, normalizando las
fechas y ordenando por ID: todos coinciden. Clientes y Órdenes se consultaron
con `limite=100` para incluir sus 25 filas, en lugar de solo la primera página.
Los cuatro GET respondieron `200`.

`GET /docs` respondió `200`. El `openapi.json` servido por la imagen construida
contiene las 19 operaciones de negocio con resumen y descripción explícitos.

Hay un segundo proyecto Docker con PostgreSQL publicado en `127.0.0.1:5432`.
Conectarse a ese puerto no consulta la base verificada aquí. Para este Compose,
VS Code o pgAdmin deben usar `127.0.0.1:15432` y la base y usuario de `.env`.
Dentro de la red de Compose, la API sigue usando `db:5432`.

No se ejecutaron seeders, comandos de borrado, `down -v`, cambios de contraseña
ni importaciones sobre los registros existentes. No se hizo `git pull` ni se
integraron otras ramas. La observación R04 sigue pendiente porque la imagen
no identifica el campo ni la longitud solicitada.

## Trazabilidad pendiente

Al revisar y guardar estos cambios, registrar aquí el commit y el PR reales.
No se han creado commits, publicado cambios ni actualizado Trello en esta tarea.
