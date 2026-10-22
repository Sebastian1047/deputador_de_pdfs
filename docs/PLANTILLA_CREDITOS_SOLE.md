# Excel Creditos SOLE 2026 → Google Sheets en Drive

Se analizó el archivo proporcionado sin modificarlo. Contiene:

| Pestaña | Estructura | Función |
| --- | --- | --- |
| DETALLE DEVOLUCION | 97 filas de registros + encabezados | Destino para anexar nuevos PDF |
| SUMA TOTAL | Resumen por PO, CR y SP filtrado por MES=3 | Reporte existente |

Columnas exactas de **DETALLE DEVOLUCION**: `VARIEDAD`, `CAT`, `FINCA`, `RM`, `TOTAL`, `QC Inspection`, `MES`. Las últimas cuatro son numéricas. La etiqueta del Excel `QC Inspection ` tiene un espacio al final; el conector lo acepta al validar.

## Subir y convertir sin perder el original

1. Abrir https://drive.google.com/ con la cuenta propietaria de la hoja de prueba.
2. **Nuevo → Subir archivo** y seleccionar `Creditos SOLE 2026.xlsx`.
3. Una vez cargado, abrir el documento en Drive con Google Sheets.
4. Seleccionar **Archivo → Guardar como Hojas de cálculo de Google**. Se crea una copia **nativa**; el original `.xlsx` permanece sin modificar.
5. Abrir la nueva hoja de Google Sheets y comprobar que existan `DETALLE DEVOLUCION` y `SUMA TOTAL`, con sus 97 filas y el resumen por PO/CR/SP del mes 3. Comprobar que Google Sheets conservó correctamente la tabla dinámica del resumen y ajustar su rango a columnas completas si fuera necesario para incluir futuras filas.
6. Guardar el vínculo de la nueva hoja para extraer su ID desde el segmento `/d/<ID>/edit`. No compartir públicamente el archivo si contiene datos reales.

Esta integración escribe **solamente en el nuevo Google Sheets**, no en el Excel `.xlsx` original. El archivo de Drive debe ser una hoja de cálculo de Google y no solo un Excel abierto en modo compatible.

Fuente: https://support.google.com/docs/answer/9331167?hl=es

## Preparar conexión en Render

- Crear una cuenta de servicio en el proyecto Google Cloud si está permitido y habilitar Google Sheets API.
- Compartir **solo la nueva hoja** con el correo de la cuenta de servicio con permiso Editor.
- Guardar el contenido de la clave JSON únicamente como variable secreta `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` en Render. La clave no debe compartirse por chat ni publicarse en GitHub.
- Guardar `GOOGLE_SPREADSHEET_ID` con el ID de la nueva hoja.
- El Blueprint tiene `TABLE_PROVIDER=google_sheets`, `GOOGLE_SHEET_TAB=DETALLE DEVOLUCION` y `GOOGLE_SHEETS_TEMPLATE=creditos_sole`.

La primera operación de análisis validará los siete encabezados y creará la hoja oculta `_CONTROL_PDF`, donde se registran identificadores de PDF y fechas. La fila histórica de datos no se sobrescribe. El guardado de nueva fila y marca de control usa una única solicitud `spreadsheets.batchUpdate`.

**Advertencias:** el resumen `SUMA TOTAL` debe comprobarse para detectar si su tabla dinámica incluye filas añadidas. Los 97 registros históricos no tienen claves de PDF, por lo que solo se detectan automáticamente duplicados de PDF que la aplicación haya registrado desde la primera prueba.

## Pendiente antes de procesar PDF

Se analizó un PDF de muestra **QC Inspection** de dos páginas: la primera contiene texto digital y la segunda fotos. No se requiere OCR para el ejemplo. El nuevo extractor `depurador/sole_pdf.py` completa las siete columnas así:

- VARIEDAD = Product completo.
- CAT = PO si Pom, SP si Mums Spider, CR si Mums Cremon.
- FINCA = JN si el proveedor empieza por JN (ej. JN-San Nicolas).
- RM = Credit Quantity, cantidad de bunches.
- TOTAL = Total Credit, incluyendo cargos de flete (no solo Flower Credit).
- QC Inspection = Credit #.
- MES = mes de Credit Date.

`config/campos.json` ya define este formato y los siete encabezados. Se rechazan productos o proveedores no reconocidos. La aplicación también lee la columna F original y no agrega créditos cuyo número QC ya figure en los datos históricos, aunque no aparezcan en `_CONTROL_PDF`.

La prueba local con el archivo de muestra fue satisfactoria; **no se subió el PDF real a GitHub**. Falta crear el servicio en Render, conectar Gmail y Google Sheets y verificar escritura solo en una copia de prueba.

**No utilizar datos reales empresariales o personales en Render Free sin autorización del propietario y controles adecuados.** Render Free suspende el servicio y pierde archivos locales temporales, incluido el token Gmail.
