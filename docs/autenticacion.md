# Contrato de usuarios y sesiones

Base para las tarjetas de login, refresh y recuperación. Todavía no hay rutas
de autenticación ni cuentas creadas. Se mantiene la estructura actual por capas.

| Entidad | Contrato |
|---|---|
| Usuario | Identidad independiente de Cliente. Correo normalizado único, hash de contraseña, rol "operador" o "admin", estado y "version_tokens". |
| Sesión | Cada refresh tendrá una fila con hash único, familia, versión del usuario y fechas UTC de creación, expiración, consumo y revocación. |

"UsuarioRegistro" acepta correo y contraseña de 12 a 128 caracteres; rechaza
rol, estado y otros campos extra. "UsuarioLogin" acepta correo y contraseña.
"UsuarioResponse" devuelve solo ID, correo, rol y estado. El registro público
usará siempre el rol "operador". La contraseña no se recorta ni se normaliza.

Contrato para la siguiente tarjeta: POST "/auth/registro" devuelve 201 y
"UsuarioResponse"; POST "/auth/login", 200 con "access_token" y "token_type"
"bearer"; GET "/auth/me", 200 con "UsuarioResponse" usando Bearer.
Acceso sin identidad válida: 401; usuario válido sin permiso: 403.

Los repositorios reciben hashes, nunca contraseñas o refresh en claro.
El hasher Argon2id y los permisos HTTP se implementan en la siguiente tarjeta.
Propuesta de permisos: ambos roles consultan y crean/actualizan trabajo del
taller; solo admin elimina clientes, vehículos o reparaciones.

El access JWT deberá validar firma, algoritmo, sujeto, expiración, propósito
y coincidencia de "version_tokens" con el usuario activo en cada petición.
Cambiar la contraseña o desactivar la cuenta incrementa esa versión y revoca
todas sus sesiones en una transacción. Así la próxima tarjeta podrá rechazar
tokens anteriores; esta base todavía no emite ni valida JWT.

El consumo de refresh usa un UPDATE condicional: dos solicitudes no pueden
consumir la misma fila. La tarjeta de refresh añadirá el reemplazo en la misma
transacción, conservará la familia y revocará esa familia ante reutilización.
La recuperación de contraseña y sus permisos de uso único quedan en su tarjeta.

Aplicar "alembic upgrade head" antes de iniciar la API. La revisión "0002"
añade usuarios/sesiones; no modifica los datos del taller ni crea un admin.
"downgrade 0001" elimina esas dos tablas y sus cuentas/sesiones.

Referencia de clase: [solución del profesor](https://github.com/DrSolonius/JWT_auth_backend/tree/feat/aprobacion-cuentas-admin).
Se usan dos roles explícitos; la aprobación administrativa opcional no se incluye.
