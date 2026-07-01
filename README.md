# PDF-TO-MARKDOWN-CLASSIC-GREEK

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21104928.svg)](https://doi.org/10.5281/zenodo.21104928)

Convierte un PDF con texto en griego clásico (y/o inglés, francés, italiano, etc.) a un archivo Markdown (`.md`) usando reconocimiento óptico de caracteres (OCR), corrigiendo después los errores típicos del OCR en griego.

> **¿No tienes conocimientos de informática?** Sáltate todo lo de más abajo (clonar el repositorio, terminal, Python...) y ve directamente a la sección **["Para compañeros sin conocimientos de informática (sin Git, sin terminal)"](#para-compañeros-sin-conocimientos-de-informática-sin-git-sin-terminal)**, donde se explica cómo descargar y usar la aplicación con doble clic, sin código de por medio.
>
> Eso sí: **tanto si usas el código como si usas la aplicación con doble clic, es obligatorio instalar Tesseract OCR y Poppler aparte** (no van incluidos ni en el repositorio ni dentro del `.exe`/`.app`, son programas externos). No hay forma de saltarse ese paso; los enlaces de descarga y el comando de cada sistema operativo están explicados en esa misma sección.

## Cómo citar este software

Si usas esta herramienta en tu investigación, cítala como:

> Candel Lozano, C. (2026). *PDF-TO-MARKDOWN-CLASSIC-GREEK: conversión de PDF a Markdown con OCR y corrección automática para griego clásico* (v1.4) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21104928

En formato BibTeX:

```bibtex
@software{candel_lozano_2026_pdf_to_markdown,
  author       = {Candel Lozano, Carlos},
  title        = {{PDF-TO-MARKDOWN-CLASSIC-GREEK: conversión de PDF
                   a Markdown con OCR y corrección automática para
                   griego clásico}},
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v1.4},
  doi          = {10.5281/zenodo.21104928},
  url          = {https://doi.org/10.5281/zenodo.21104928}
}
```

Los metadatos completos (autor, licencia, palabras clave) también están disponibles en el archivo [`CITATION.cff`](./CITATION.cff) de este repositorio, y GitHub los muestra directamente con el botón **"Cite this repository"** en la barra lateral.

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
| `gui_common.py` | Motor de conversión y componentes compartidos por las dos aplicaciones de escritorio. |
| `tema_calido.json` | Tema visual (tonos ámbar/marrón) de las aplicaciones de escritorio. |
| `ocr_postprocess_mejorado.py` | Corrige errores típicos del OCR en griego clásico y en el texto académico multilingüe que lo acompaña. |
| `pdf_table_extractor.py` | Extrae tablas de PDFs digitales (con `pdfplumber`) o escaneados (con OpenCV + Tesseract), con detección estricta. |
| `config.py` | Configuración centralizada de las rutas de Tesseract y Poppler (vía variables de entorno). |

## Requisitos previos

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (con los paquetes de idioma que necesites, por ejemplo `grc` para griego clásico)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) (en Windows; en Linux/macOS suele bastar con instalarlo por el gestor de paquetes del sistema)

### Clonar el repositorio

Abre una terminal (en Windows, Git Bash; en Linux/macOS, la Terminal normal) y ejecuta, uno a uno:

```bash
git clone https://github.com/candellozanocarlos/PDF-TO-MARKDOWN-CLASSIC-GREEK.git
```

Esto crea una carpeta nueva llamada `PDF-TO-MARKDOWN-CLASSIC-GREEK` con una copia completa del repositorio. Entra en ella:

```bash
cd PDF-TO-MARKDOWN-CLASSIC-GREEK
```

Todos los comandos de las secciones siguientes (`pip install`, `python pdf_to_markdown.py`, etc.) se ejecutan **desde dentro de esta carpeta**. Si en algún momento un comando da "No such file or directory" o "command not found", lo primero a comprobar es que sigues dentro de `PDF-TO-MARKDOWN-CLASSIC-GREEK` (con `pwd` en Linux/macOS o simplemente mirando la ruta que muestra el símbolo `$` en Git Bash).

Si más adelante quieres actualizar tu copia local con los últimos cambios subidos al repositorio, hazlo con:

```bash
git pull
```

### Instalar las dependencias de Python

```bash
pip install -r requirements.txt
```

### Instalar y configurar Tesseract y Poppler

El proyecto necesita dos programas externos que **no son librerías de Python** (por eso `pip install -r requirements.txt` no los instala):

- **Tesseract OCR**: el motor que "lee" el texto dentro de las imágenes de cada página del PDF. Sin él, no hay conversión posible.
- **Poppler**: la librería que convierte cada página del PDF en una imagen antes de pasársela a Tesseract (la usa `pdf2image` por debajo).

#### Paso 1 — Instalarlos

**Windows:**
1. Tesseract: descarga el instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) y ejecútalo. Durante la instalación, marca el paquete de idioma "Greek" (griego clásico) además del inglés si lo ofrece la lista de idiomas adicionales.
2. Poppler: descarga el `.zip` desde [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) y descomprímelo en una carpeta fija, por ejemplo `C:\poppler` (Poppler para Windows no trae instalador, es solo un `.zip` con los ejecutables dentro).

**macOS**, con [Homebrew](https://brew.sh) instalado:
```bash
brew install tesseract tesseract-lang poppler
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt install tesseract-ocr tesseract-ocr-grc poppler-utils
```
(`tesseract-ocr-grc` es el paquete de idioma griego; añade `tesseract-ocr-fra`, `tesseract-ocr-deu`, etc. según los idiomas que necesites.)

#### Paso 2 — Comprobar que el proyecto los encuentra automáticamente

`config.py` intenta localizarlos solo, sin que tengas que configurar nada, buscando: el `PATH` del sistema, y en macOS además las carpetas típicas de Homebrew/MacPorts. En la mayoría de los casos con esto basta. Para comprobarlo, ejecuta:

```bash
python -c "import config; print(config.verificar_dependencias_externas())"
```

- Si imprime `[]` (una lista vacía), todo en orden, puedes saltar directamente a la sección "Uso" de más abajo.
- Si imprime uno o más mensajes de aviso, significa que no ha encontrado alguno de los dos programas y te dice cómo instalarlo; si ya los tienes instalados pero en una ruta poco habitual, sigue con el Paso 3.

#### Paso 3 — Solo si el Paso 2 no los encontró: indicar la ruta manualmente

Se hace con dos variables de entorno, **`TESSERACT_CMD`** (ruta al ejecutable de Tesseract) y **`POPPLER_PATH`** (ruta a la *carpeta* `bin` de Poppler, no al ejecutable). Hay que definirlas en la misma terminal donde vayas a ejecutar el script, cada vez que abras una terminal nueva (o añadirlas de forma permanente al perfil de tu shell, `.zshrc`/`.bashrc`/perfil de PowerShell, si no quieres repetirlo).

**Windows (Git Bash o PowerShell):**
```bash
export TESSERACT_CMD="/c/Program Files/Tesseract-OCR/tesseract.exe"
export POPPLER_PATH="/c/poppler/Library/bin"
```
o, en PowerShell:
```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:POPPLER_PATH  = "C:\poppler\Library\bin"
```

**Linux / macOS:**
```bash
export TESSERACT_CMD=/usr/bin/tesseract
export POPPLER_PATH=/usr/bin
```
(ajusta la ruta a donde tengas realmente instalados los programas; en Mac con Homebrew suele ser `/opt/homebrew/bin` en chips Apple o `/usr/local/bin` en chips Intel).

Vuelve a ejecutar el comando de comprobación del Paso 2 para confirmar que ahora sí los encuentra.

---

**Con esto, la instalación está completa.** El siguiente paso es la sección "Uso" de aquí abajo, donde se ejecuta ya la conversión propiamente dicha.

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

## Para compañeros sin conocimientos de informática (sin Git, sin terminal)

Si vas a compartir esta herramienta con alguien que no sabe qué es Git ni una terminal, **no le mandes este repositorio para que lo clone**: mándale directamente un `.exe` a través de la sección "Releases" de GitHub. Así su experiencia se reduce a: descargar un archivo, hacer doble clic, y usar la ventana.

### Lo que tiene que hacer la persona que lo use (nada de código)

**Requisito previo, una sola vez:** aunque el `.exe`/`.app` lleva empaquetado todo el código Python, **no lleva Tesseract ni Poppler** (son programas externos, no bibliotecas de Python, así que PyInstaller no los incluye). Hay que instalarlos aparte una vez:

- **Windows:**
  1. Tesseract OCR: descargar el instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) y ejecutarlo (dejar las opciones por defecto; asegúrate de marcar el paquete de idioma griego, "Greek", si el instalador lo ofrece como opción).
  2. Poppler: descargar el `.zip` desde [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases), descomprimirlo en, por ejemplo, `C:\poppler`.
  3. Si la aplicación no los encuentra automáticamente, definir las variables de entorno `TESSERACT_CMD` y `POPPLER_PATH` (Panel de control → Sistema → Configuración avanzada → Variables de entorno) apuntando a la ruta del `.exe` de Tesseract y a la carpeta `bin` de Poppler respectivamente.

- **macOS:** con [Homebrew](https://brew.sh) instalado, abrir la aplicación Terminal (viene con macOS) y ejecutar una sola vez:
  ```bash
  brew install tesseract tesseract-lang poppler
  ```
  (`tesseract-lang` incluye el paquete de griego clásico y otros idiomas; sin él, Tesseract solo reconoce inglés.)

Si te falta alguno de los dos, la aplicación lo detecta al intentar convertir y te lo dice claramente en el propio registro de la ventana (con instrucciones de instalación), en vez de fallar con un error críptico.

**Uso normal, una vez instalado lo anterior:**

1. Entra en la página de **Releases** del repositorio (enlace fijado en la barra lateral derecha de GitHub, o en `.../releases`).
2. Descarga el archivo correspondiente a tu sistema y a lo que necesites: `.exe` en Windows, `.zip` con un `.app` dentro en macOS ("PDF a Markdown" para texto, o "PDF a Markdown (con tablas)" si también necesita tablas).
3. Ábrelo:
   - **Windows:** doble clic. Probablemente aparezca un aviso de SmartScreen ("Windows protegió tu PC") porque el `.exe` no está firmado digitalmente; pulsa **"Más información"** → **"Ejecutar de todos modos"**. Esto es normal en programas de un solo desarrollador sin certificado de pago, no significa que el programa sea inseguro.
   - **macOS:** descomprime el `.zip`, y para el primer uso haz clic derecho sobre el `.app` → "Abrir" (en vez de doble clic normal), para saltar el aviso de "desarrollador no verificado". A partir de ahí, doble clic funciona con normalidad.
4. Usa la ventana con normalidad: seleccionar PDF, carpeta de salida, idiomas, y pulsar "Convertir".

### Lo que tienes que hacer tú una vez (para dejar el .exe publicado)

Esto sí requiere terminal, pero solo lo haces tú, una vez, no cada compañero:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "PDF a Markdown" ^
    --add-data "tema_calido.json;." ^
    PDF_a_Markdown_GUI.py

pyinstaller --onefile --windowed --name "PDF a Markdown (con tablas)" ^
    --add-data "tema_calido.json;." ^
    PDF_a_Markdown_con_Tablas_GUI.py
```

(`config.py` no necesita `--add-data`: al ser un módulo Python que se importa con `import config`, PyInstaller lo detecta e incluye automáticamente. Solo `tema_calido.json`, al ser un archivo de datos, necesita indicarse explícitamente.)

(En Git Bash el separador de `--add-data` en Windows es `;`, como arriba; en Linux/macOS sería `:`. El símbolo `^` al final de línea es el de continuación de línea de `cmd.exe`; en Git Bash usa `\` en su lugar si copias el comando literal.)

Esto genera los `.exe` dentro de `dist/`. Después:

1. Ve a la página del repositorio en GitHub → pestaña **"Releases"** (o el enlace "Create a new release" que aparece en la barra lateral) → **"Draft a new release"**.
2. Ponle una etiqueta de versión (p. ej. `v1.0`) y un título.
3. Arrastra los dos archivos `.exe` generados en `dist/` a la zona de "Attach binaries".
4. Pulsa **"Publish release"**.

A partir de ahí, el enlace a esa página de Releases es lo único que necesitas compartir con tus compañeros.

## Aplicaciones de escritorio (detalle técnico)

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

Ambas comparten:

- **Tema visual cálido** (`tema_calido.json`, tonos ámbar/marrón sobre fondo crema), aplicado globalmente vía `ctk.set_default_color_theme(...)` en `gui_common.py`. Para cambiar la paleta basta con editar ese único archivo JSON.
- **Selector de idiomas por casillas independientes** (griego clásico, inglés, francés, alemán, italiano, español, latín): se marcan y desmarcan libremente según lo que aparezca en el PDF, en vez de elegir entre combinaciones prefijadas. Al menos un idioma debe quedar marcado.

Para instrucciones de empaquetado con PyInstaller y publicación como `.exe` descargable, ver la sección anterior "Para compañeros sin conocimientos de informática".

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
