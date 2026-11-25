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

Para la clase, usar esa referencia en Kubero, configurar PostgreSQL y los
secretos del backend, aplicar "alembic upgrade head" y comprobar el puerto
interno 8000, HTTPS y el acceso con y sin token.
