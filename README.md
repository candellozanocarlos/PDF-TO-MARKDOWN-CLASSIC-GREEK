# PDF-TO-MARKDOWN-CLASSIC-GREEK

Convierte un PDF con texto en griego clásico (y/o inglés, francés, italiano, etc.) a un archivo Markdown (`.md`) usando reconocimiento óptico de caracteres (OCR), corrigiendo después los errores típicos del OCR en griego.

## Por qué Markdown y no otro formato

Un PDF es, en esencia, una imagen fija: una IA (Claude, ChatGPT, Gemini...) no puede leer su contenido directamente. Hay que extraer el texto primero y guardarlo en un formato que la IA entienda bien.

- **Texto puro** — sin capas de formato binario como `.docx` o `.pdf`; se lee de principio a fin sin esfuerzo.
- **Mantiene la estructura** — títulos, listas, negritas, etc. se marcan con símbolos simples, así la IA distingue jerarquía en vez de ver una masa de texto plana.
- **Es el formato nativo de Claude** — el diálogo entre el texto y la IA es más directo y preciso.
- **Ocupa muy poco espacio** — un PDF de 10 MB puede quedar en pocos KB, dejando más margen en la ventana de contexto.
- **Universal y duradero** — cualquier editor de texto lo abre, sin depender de licencias ni versiones de software.

Flujo de trabajo habitual:

```
PDF (original) → .md (este script) → pegarlo/subirlo a Claude → resumir, traducir, analizar, extraer datos...
```

## Requisitos previos

- Python 3.x
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases)
- Librerías Python:

  ```bash
  pip install pytesseract pdf2image
  ```

## Uso

1. Abre `PDF_TO_MARKDOWN_comentado.py` y edita las líneas marcadas con `<<< CAMBIA ESTO`:
   - `PDF_DIR` — carpeta donde está el PDF de entrada.
   - `OUTPUT_DIR` — carpeta donde se guardará el `.md` (se crea si no existe).
   - `PDF_NAME` — nombre exacto del PDF a convertir.
2. Guarda el archivo.
3. Ejecuta:

   ```bash
   python PDF_TO_MARKDOWN_comentado.py
   ```

4. El `.md` resultante se abre automáticamente al terminar.

### Configuración de idiomas

El OCR usa `lang="eng+grc"` (inglés + griego clásico) por defecto. Puedes añadir otros idiomas instalados en Tesseract (`fra`, `deu`, `ita`...) o dejar solo `"grc"` si el documento es íntegramente griego. La lista completa de idiomas disponibles está en la carpeta indicada por `TESSDATA_DIR`.

## Cómo funciona

1. **Conversión a imágenes** — cada página del PDF se convierte en una imagen a 300 ppp con `pdf2image`/Poppler.
2. **OCR página a página** — Tesseract extrae el texto de cada imagen.
3. **Corrección de errores** — `ocr_postprocess_mejorado.corregir_texto()` limpia errores típicos del OCR en griego clásico.
4. **Guardado** — el texto corregido de todas las páginas se une (con separador `--- Página N ---`) y se guarda en UTF-8 como `.md`.

## Rutas por defecto (editables en el script)

| Variable | Descripción |
|---|---|
| `pytesseract.pytesseract.tesseract_cmd` | Ruta al ejecutable de Tesseract |
| `TESSDATA_DIR` | Carpeta con los datos de idioma de Tesseract |
| `POPPLER_PATH` | Carpeta `bin` de Poppler |
