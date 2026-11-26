# Validación de la imagen para Kubero UCT

El workflow Backend CI ejecuta Ruff, comprueba el formato, construye Docker,
ejecuta las pruebas con PostgreSQL temporal y exige 85 % de cobertura del backend.
El reporte XML queda en el artefacto "coverage".

En GitHub, protege "main" y exige el check "Validate backend" y una revisión
antes del merge. Primero deja que se ejecute el workflow en el PR para que el
check aparezca al configurar la regla.

Al integrar en "main", el workflow vuelve a validar y publica en GHCR
exactamente la imagen probada, etiquetada con el SHA completo. La referencia
aparece en el resumen del job "Publish validated image". Kubero debe tener
permiso de lectura del paquete si es privado.

## Autodespliegue de taller-mecanico

Al publicar, CI también actualiza la etiqueta `latest`. Después de la primera
publicación de esa etiqueta, selecciónala una vez en Kubero y comprueba que el
pod queda listo. Guarda el token de Kubero como secreto de Actions
`KUBERO_TOKEN` y crea la variable de Actions `KUBERO_AUTODEPLOY` con valor
`true`. Desde el próximo merge validado, CI pedirá el reinicio de la app
`taller-mecanico` en el pipeline del mismo nombre y fase `production`.
Un HTTP 200 confirma la solicitud. Comprueba después Swagger y el estado del
pod. Puedes volver al SHA anterior desde Kubero si necesitas revertir.

Para la clase, usar esa referencia en Kubero, configurar PostgreSQL y los
secretos del backend, aplicar "alembic upgrade head" y comprobar el puerto
interno 8000, HTTPS y el acceso con y sin token.
