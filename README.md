# PDF-TO-MARKDOWN-CLASSIC-GREEK

Convierte un PDF con texto en griego clásico (y/o inglés, francés, italiano, etc.) a un archivo Markdown (`.md`) usando reconocimiento óptico de caracteres (OCR), corrigiendo después los errores típicos del OCR en griego.

## Por qué Markdown y no otro formato

Un PDF es, en esencia, una imagen fija: una IA (Claude, ChatGPT, Gemini...) no puede leer su contenido directamente. Hay que extraer el texto primero y guardarlo en un formato que la IA entienda bien.

- **Texto puro** (sin capas de formato binario como `.docx` o `.pdf`), se lee de principio a fin sin esfuerzo.
- **Mantiene la estructura**: títulos, listas, negritas, etc. se marcan con símbolos simples, así la IA distingue jerarquía en vez de ver una masa de texto plana.
- **Es el formato nativo de Claude**: el diálogo entre el texto y la IA es más directo y preciso.
- **Ocupa muy poco espacio**: un PDF de 10 MB puede quedar en pocos KB, dejando más margen en la ventana de contexto.
- **Universal y duradero**: cualquier editor de texto lo abre, sin depender de licencias ni versiones de software.

Flujo de trabajo habitual:

```
PDF (original) → .md (este script) → pegarlo/subirlo a Claude → resumir, traducir, analizar, extraer datos...
```

## Estructura del proyecto

| Archivo | Función |
| --- | --- |
| `pdf_to_markdown.py` | Script principal (CLI). Convierte el PDF completo, un rango de páginas, y opcionalmente extrae tablas. |
| `PDF_a_Markdown_GUI.py` | Aplicación de escritorio (sin terminal), solo texto. |
| `PDF_a_Markdown_con_Tablas_GUI.py` | Aplicación de escritorio (sin terminal), texto + extracción estricta de tablas. |
| `gui_common.py` | Motor de conversión compartido por las dos aplicaciones de escritorio. |
| `ocr_postprocess_mejorado.py` | Corrige errores típicos del OCR en griego clásico y en el texto académico multilingüe que lo acompaña. |
| `pdf_table_extractor.py` | Extrae tablas de PDFs digitales (con `pdfplumber`) o escaneados (con OpenCV + Tesseract), con detección estricta. |
| `config.py` | Configuración centralizada de las rutas de Tesseract y Poppler (vía variables de entorno). |

## Requisitos previos

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (con los paquetes de idioma que necesites, por ejemplo `grc` para griego clásico)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) (en Windows; en Linux/macOS suele bastar con instalarlo por el gestor de paquetes del sistema)
- Dependencias de Python:

  ```
  pip install -r requirements.txt
  ```

### Configurar las rutas de Tesseract y Poppler

En vez de editar el código, define estas variables de entorno antes de ejecutar el script (ver `config.py` para más detalle):

**Windows (PowerShell)**

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:POPPLER_PATH  = "C:\poppler\Library\bin"
```

**Linux / macOS** (normalmente ya están en el `PATH` tras instalar los paquetes del sistema, así que esto suele ser opcional)

```bash
export TESSERACT_CMD=/usr/bin/tesseract
export POPPLER_PATH=/usr/bin
```

## Uso

Documento completo:

```bash
python pdf_to_markdown.py "articulo.pdf" -o ./markdown --lang eng+grc
```

Solo un rango de páginas:

```bash
python pdf_to_markdown.py "libro.pdf" -o ./markdown --lang grc+eng+fra --paginas 79-130
```

Con extracción de tablas (detecta automáticamente si el PDF es digital o escaneado):

```bash
python pdf_to_markdown.py "articulo.pdf" -o ./markdown --tablas
```

Ver todas las opciones:

```bash
python pdf_to_markdown.py --help
```

El `.md` resultante se guarda en la carpeta de salida indicada con `-o` y se abre automáticamente al terminar (usa `--no-abrir` para desactivarlo; en Linux/macOS se abre con `xdg-open`/`open` si están disponibles).

### Configuración de idiomas

El OCR usa `--lang eng+grc` (inglés + griego clásico) por defecto. Puedes añadir otros idiomas instalados en Tesseract (`fra`, `deu`, `ita`...) o dejar solo `grc` si el documento es íntegramente griego.

## Aplicaciones de escritorio (sin terminal)

Para compartir la herramienta con compañeros que no usan la línea de comandos, hay dos aplicaciones gráficas independientes (mismo motor de conversión por debajo, en `gui_common.py`):

| Aplicación | Cuándo usarla |
| --- | --- |
| `PDF_a_Markdown_GUI.py` | Documentos de solo texto, sin tablas. Más rápida y sencilla. |
| `PDF_a_Markdown_con_Tablas_GUI.py` | Documentos que además tienen tablas. Extrae y detecta tablas con criterios **estrictos** (ver más abajo) para evitar falsos positivos. |

Ambas se ejecutan con:

```bash
python PDF_a_Markdown_GUI.py
python PDF_a_Markdown_con_Tablas_GUI.py
```

Para distribuirlas como `.exe` sin que el destinatario necesite instalar Python, puede empaquetarse con PyInstaller, por ejemplo:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "PDF a Markdown" PDF_a_Markdown_GUI.py
pyinstaller --onefile --windowed --name "PDF a Markdown (con tablas)" PDF_a_Markdown_con_Tablas_GUI.py
```

### Detección estricta de tablas

`PDF_a_Markdown_con_Tablas_GUI.py` (y `pdf_to_markdown.py --tablas`) solo consideran que hay una tabla si se cumple **todo** lo siguiente:

- La página contiene un pie explícito de **tabla** (no de figura): "Table 1", "Tabla 1", "Tab. 1", "Cuadro 1", "Tableau 1"... (los pies de figura, "Figure"/"Fig."/"Abb.", quedan excluidos a propósito).
- La rejilla tiene al menos 3 filas y 2 columnas, con al menos un 75-80 % de las filas compartiendo el mismo número de columnas.
- Al menos la mitad de las celdas contienen texto real tras el OCR (descarta recuadros vacíos o mal detectados).
- En PDFs escaneados, además: al menos 4 líneas horizontales y 3 verticales detectadas (un simple marco decorativo con solo borde exterior no cumple este mínimo), y la región debe ocupar al menos un 2 % del área de la página.

Si un documento no tiene tablas reales, es normal y esperable que la aplicación informe "0 tablas encontradas": no fuerza a encontrar algo que no está.



## Cómo funciona

1. **Conversión a imágenes**: cada página del PDF (o el rango indicado) se convierte en una imagen a 300 ppp con `pdf2image`/Poppler.
2. **OCR página a página**: Tesseract extrae el texto de cada imagen.
3. **Extracción de tablas** (opcional, con `--tablas`): `pdf_table_extractor.py` detecta si el PDF es digital o escaneado y extrae las tablas asociadas a un caption ("Tabla 1", "Table 2"...), insertándolas junto a su caption en el Markdown final.
4. **Corrección de errores**: `ocr_postprocess_mejorado.corregir_texto()` limpia errores típicos del OCR en griego clásico y en el texto académico circundante.
5. **Guardado**: el texto corregido de todas las páginas se une (con separador `--- Página N ---`) y se guarda en UTF-8 como `.md`.

## Sobre el postprocesador de OCR

`ocr_postprocess_mejorado.py` separa las reglas de corrección en tres grupos:

- `REGEX_RULES_GENERAL`: reglas genéricas y reutilizables (sigma final, ligaduras, guiones de fin de línea, notación epigráfica Leiden...).
- `REGEX_RULES_CORPUS_ESPECIFICO`: correcciones ad hoc aprendidas de documentos concretos ya procesados (nombres propios, fragmentos de palabras muy específicos). No se aplican por defecto; actívalas con `corregir_texto(texto, incluir_corpus_especifico=True)` solo si vas a reprocesar el mismo corpus de siempre.
- `REGEX_RULES_GRIEGO`: reglas específicas para bloques de texto en griego.

## Limitaciones conocidas

- La extracción de tablas en PDFs escaneados asume tablas con bordes explícitos (líneas horizontales y verticales visibles); tablas sin bordes no se detectan.
- `os.startfile()` (apertura automática del `.md`) es específico de Windows; en otros sistemas se usa `open`/`xdg-open` como alternativa best-effort.
