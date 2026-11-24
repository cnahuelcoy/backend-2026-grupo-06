# Autenticación

| Ruta | Uso |
|---|---|
| POST "/auth/registro" | Correo y "password" de 12 a 128 caracteres. Crea un operador; no acepta rol ni estado. |
| POST "/auth/login" | Mismos campos. Devuelve "access_token" y "token_type": "bearer". |
| GET "/auth/me" | Consulta la cuenta usando "Authorization: Bearer <access_token>". |

Las contraseñas usan Argon2id; nunca se devuelven en respuestas ni errores.
Los correos se normalizan y son únicos. Cinco fallos bloquean la cuenta durante
15 minutos; los intentos se guardan en BD mediante un UPDATE atómico.
El error de login es el mismo para cuenta inexistente, inactiva o bloqueada.

El access dura 15 minutos por defecto, configurable entre 1 y 30 mediante
"JWT_ACCESS_MINUTES". Usa HS256 y valida firma, algoritmo, "sub", "exp", "iat",
propósito "access" y "ver" contra la versión actual del usuario activo.
Cambiar la contraseña o desactivar la cuenta invalida sus tokens anteriores.

Todas las operaciones del taller requieren Bearer. Operador y admin pueden
consultar, crear y actualizar; solo admin elimina clientes, vehículos o
reparaciones. Sin identidad válida: 401; sin permiso: 403.
En ambos casos el mensaje es "Acceso bloqueado", sin mencionar el rol.

## Configuración y administrador

Generar "JWT_SECRET_KEY" en el archivo ignorado ".env":

```powershell
uv run --no-sync python scripts/configurar_auth.py
```

Con la imagen construida, aplicar "alembic upgrade head" antes de arrancar.
La revisión "0003" añade intentos y bloqueo sin borrar cuentas ni datos del taller.
Completar "ADMIN_EMAIL" y "ADMIN_PASSWORD" en ".env", nunca en ".env.example".
La contraseña debe tener de 12 a 128 caracteres; usar comillas simples si incluye
"$" o "#" para que Compose la interprete literalmente. Luego reconstruir y recrear:

```powershell
docker compose up -d --build backend
```

Al arrancar crea el admin o sincroniza su contraseña con la configuración;
en PostgreSQL guarda solo el hash. Cambiarla invalida los tokens y sesiones
anteriores. Sin cambios conserva el hash, la versión y el bloqueo de login.
Con "ADMIN_PASSWORD" vacío no crea admin. "docker compose restart" no recarga
los cambios de ".env"; hay que recrear el servicio. En Swagger, usar "/auth/login"
y pegar el "access_token" en "Authorize" (HTTPBearer).

"usuarios" es independiente de "clientes". "sesiones" conserva hash de refresh,
familia, versión y fechas UTC. Refresh, logout, cookies, CSRF y recuperación
siguen en sus propias tarjetas; todavía no hay esas rutas.

Referencia: [ejemplo del profesor](https://github.com/DrSolonius/JWT_auth_backend/tree/feat/aprobacion-cuentas-admin).
