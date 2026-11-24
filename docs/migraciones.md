# Migraciones con Alembic

Para manejar la estructura de la base de datos usamos Alembic. La migración
inicial (`0001`) crea las cuatro tablas del proyecto: `clientes`, `vehiculos`,
`ordenes_trabajo` y `reparaciones`, con sus claves primarias, claves foráneas,
restricciones `UNIQUE` (email y patente) y los `CHECK` de los enums
(estado de la orden y tipo de reparación).

La revisión `0002` añade `usuarios` y `sesiones`, sin cambiar las cuatro tablas
del taller. El contrato está en [autenticacion.md](autenticacion.md).

Alembic usa la misma URL de base de datos que la API (`DATABASE_URL` en
`database/session.py`). Si no se define la variable, se usa
`sqlite:///./taller_mecanico.db`.

## Aplicar las migraciones

Desde la raíz del proyecto:

```bash
uv sync
uv run alembic upgrade head
```

Esto crea las tablas y deja registrada la versión en la tabla `alembic_version`.
Después se puede levantar la API como siempre:

```bash
uv run uvicorn proyectobackend.main:app --reload
```

## Ver la versión

```bash
uv run alembic current    # versión aplicada en la base de datos
uv run alembic history    # lista de migraciones
uv run alembic check      # revisa que la base coincida con los modelos
```

Si todo está bien, `current` muestra `0002 (head)` y `check` muestra
`No new upgrade operations detected.`

## Si la base ya fue creada con create_all()

Si la base se creó antes al iniciar la API (`init_db()` usa
`Base.metadata.create_all()`), las tablas ya existen pero Alembic no tiene
ninguna versión registrada. En ese caso **no hay que correr `upgrade head`**,
porque intentaría crear las tablas de nuevo y fallaría con
`table clientes already exists`.

Lo que se hace es marcar la base como si ya tuviera la migración aplicada,
sin tocar las tablas ni los datos:

```bash
cp taller_mecanico.db taller_mecanico.backup.db   # respaldo, por si acaso
uv run alembic stamp 0001
uv run alembic upgrade head
uv run alembic current    # debe mostrar 0002 (head)
uv run alembic check      # debe decir que no hay cambios
```

Usar ese `stamp 0001` solo tras comprobar que existen exactamente las tablas
y restricciones de la revisión inicial, sin historial de Alembic. Luego
`upgrade head` crea usuarios y sesiones. No marcar `head` para omitir esa migración.

## Nuevas migraciones

Cuando se cambie un modelo:

```bash
uv run alembic revision --autogenerate -m "descripcion del cambio"
uv run alembic upgrade head
```

Conviene revisar el archivo generado en `migrations/versions/` antes de aplicarlo.

## Observaciones

- `main.py` sigue llamando a `create_all()` al iniciar. Si la base ya está
  migrada no hace nada, pero si se levanta la API antes de migrar, crea las
  tablas sin registrar la migración. Revisar el esquema y su historial antes
  de decidir si corresponde usar `stamp`; no aplicarlo a ciegas.
- En SQLite las claves foráneas solo se validan si la conexión activa
  `PRAGMA foreign_keys=ON`, y `session.py` no lo hace. Las relaciones se
  validan en los services.
