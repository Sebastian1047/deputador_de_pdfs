# Procesador de PDF por correo

Aplicación en Python para consultar una cuenta de correo, leer PDF adjuntos, extraer datos y agregarlos a un archivo Excel.

## Estado actual

Se está preparando la estructura base del proyecto. **Todavía no se conecta a ningún correo ni procesa documentos reales**, porque falta definir el proveedor del correo y el destino del Excel.

## Objetivo

1. Autorizar de forma segura el acceso a una cuenta de correo.
2. Encontrar correos con archivos PDF adjuntos.
3. Leer los PDF sin guardarlos permanentemente en el equipo.
4. Extraer los campos que se definan a partir de documentos de ejemplo.
5. Validar los datos y evitar procesar el mismo documento dos veces.
6. Agregar los resultados a Excel.
7. Ejecutar el proceso manualmente o de forma programada mediante GitHub Actions.

## Requisitos

- Python 3.11 o posterior.
- Cuenta de correo con acceso mediante una API autorizada.
- Definir dónde se almacenará el Excel.

## Ejecutar la comprobación inicial

```bash
python -m app.main --check
```

## Próximas decisiones

- Proveedor: Gmail o Outlook/Microsoft 365.
- Destino del Excel: OneDrive/SharePoint, archivo generado como artefacto u otra ubicación.
- Estructura de los datos que se extraerán de los PDF.

## Seguridad

No guardes contraseñas, tokens, archivos de credenciales ni datos privados en el repositorio. Las credenciales se configurarán mediante secretos seguros cuando se implemente la conexión.
