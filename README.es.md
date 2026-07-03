# PDF-TO-MARKDOWN-CLASSIC-GREEK

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21130682.svg)](https://doi.org/10.5281/zenodo.21130682)

**[Read this in English](./README.md)**

Convierte un PDF con texto en griego clásico (y/o inglés, francés, italiano, etc.) en un archivo Markdown (`.md`) mediante reconocimiento óptico de caracteres (OCR), corrigiendo después los errores típicos del OCR en griego.

> **¿Sin conocimientos de informática?** Sáltate todo lo de abajo (clonar el repositorio, terminal, Python...) y ve directamente a la sección **["Para usuarios sin conocimientos técnicos (sin Git, sin terminal)"](#para-usuarios-sin-conocimientos-técnicos-sin-git-sin-terminal)**, que explica cómo descargar y usar la aplicación con un doble clic, sin tocar código.
>
> Dicho esto: **este proyecto también depende de Tesseract OCR y Poppler**, dos programas externos (no son librerías de Python, así que no van incluidos dentro del repositorio ni del `.exe`/`.app`). Si ejecutas el código desde el código fuente, tienes que instalarlos tú (ver "Requisitos previos" más abajo). Si usas en cambio la aplicación de doble clic, puede instalar los dos automáticamente, con un solo clic y sin terminal de por medio; ver la sección "Para usuarios sin conocimientos técnicos" para los detalles.

## Cómo citar este software

Si usas esta herramienta en tu investigación, cítala así:

> Candel Lozano, C. (2026). *PDF-TO-MARKDOWN-CLASSIC-GREEK: OCR-based PDF-to-Markdown conversion with automatic post-processing for Classical Greek* (v1.10) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21130682

En formato BibTeX:

```bibtex
@software{candel_lozano_2026_pdf_to_markdown,
  author       = {Candel Lozano, Carlos},
  title        = {{PDF-TO-MARKDOWN-CLASSIC-GREEK: OCR-based
                   PDF-to-Markdown conversion with automatic
                   post-processing for Classical Greek}},
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v1.10},
  doi          = {10.5281/zenodo.21130682},
  url          = {https://doi.org/10.5281/zenodo.21130682}
}
```

Los metadatos completos (autor, licencia, palabras clave) también están disponibles en el archivo [`CITATION.cff`](./CITATION.cff) de este repositorio, y GitHub los muestra directamente con el botón **"Cite this repository"** en la barra lateral.

## Por qué Markdown y no otro formato

Un PDF es, esencialmente, una imagen fija: una IA (Claude, ChatGPT, Gemini...) no puede leer su contenido directamente. El texto hay que extraerlo primero y guardarlo en un formato que la IA entienda bien.

- **Texto plano** (sin capas de formato binario como `.docx` o `.pdf`), que se lee de principio a fin sin esfuerzo.
- **Conserva la estructura**: los encabezados, listas, negritas, etc. se marcan con símbolos sencillos, así que la IA distingue la jerarquía en vez de ver una masa de texto plano.
- **Formato nativo de Claude**: el intercambio entre el texto y la IA es más directo y preciso.
- **Ocupa muy poco**: un PDF de 10 MB puede acabar pesando solo unos pocos KB, dejando más espacio en la ventana de contexto.
- **Universal y duradero**: cualquier editor de texto puede abrirlo, sin depender de licencias ni de versiones de software.

Flujo de trabajo típico:

```
PDF (original) → .md (este script) → pegar/subir a Claude → resumir, traducir, analizar, extraer datos...
```

## Estructura del proyecto

| Archivo | Función |
| --- | --- |
| `pdf_to_markdown.py` | Script principal (línea de comandos). Convierte el PDF entero, un rango de páginas, y opcionalmente extrae tablas. |
| `PDF_a_Markdown_GUI.py` | Aplicación de escritorio en castellano (sin terminal), solo texto. |
| `PDF_a_Markdown_con_Tablas_GUI.py` | Aplicación de escritorio en castellano (sin terminal), texto + extracción estricta de tablas. |
| `PDF_to_Markdown_GUI.py` | La misma aplicación de solo texto, en inglés. |
| `PDF_to_Markdown_with_Tables_GUI.py` | La misma aplicación con tablas, en inglés. |
| `i18n.py` | Módulo de traducción: centraliza todos los textos que se muestran en las apps, en castellano e inglés. |
| `gui_common.py` | Motor de conversión y componentes compartidos por las cuatro aplicaciones de escritorio. |
| `tema_calido.json` | Tema visual (tonos ámbar/marrón) para las aplicaciones de escritorio. |
| `ocr_postprocess.py` | Corrige errores típicos del OCR en griego clásico y en el texto académico multilingüe que suele acompañarlo. |
| `pdf_table_extractor.py` | Extrae tablas de PDFs digitales (con `pdfplumber`) o escaneados (con OpenCV + Tesseract), con detección estricta. |
| `config.py` | Configuración centralizada de las rutas de Tesseract y Poppler (vía variables de entorno), además de la instalación automática mediante Homebrew (macOS) y winget (Windows). |
| `tests/` | Batería de tests automatizados con `pytest` (tests unitarios + una pequeña prueba de extremo a extremo). |

## Requisitos previos

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (con los paquetes de idioma que necesites, por ejemplo `grc` para griego clásico)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) (en Windows; en Linux/macOS suele bastar con instalarlo con el gestor de paquetes del sistema)

### Clonar el repositorio

Abre una terminal (en Windows, Git Bash; en Linux/macOS, la Terminal normal) y ejecuta, uno a uno:

```bash
git clone https://github.com/candellozanocarlos/PDF-TO-MARKDOWN-CLASSIC-GREEK.git
```

Esto crea una carpeta nueva llamada `PDF-TO-MARKDOWN-CLASSIC-GREEK` con una copia completa del repositorio. Entra en ella:

```bash
cd PDF-TO-MARKDOWN-CLASSIC-GREEK
```

Todos los comandos de las secciones siguientes (`pip install`, `python pdf_to_markdown.py`, etc.) se ejecutan **desde dentro de esta carpeta**. Si en algún momento un comando da "No such file or directory" o "command not found", lo primero que hay que comprobar es que sigues dentro de `PDF-TO-MARKDOWN-CLASSIC-GREEK` (con `pwd` en Linux/macOS, o simplemente mirando la ruta que aparece junto al símbolo `$` en Git Bash).

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

- **Tesseract OCR**: el motor que "lee" el texto dentro de la imagen de cada página del PDF. Sin él no es posible ninguna conversión.
- **Poppler**: la librería que convierte cada página del PDF en una imagen antes de pasársela a Tesseract (la usa internamente `pdf2image`).

#### Paso 1: instálalos

**Windows:**
1. Tesseract: descarga el instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) y ejecútalo. Durante la instalación, marca el paquete de idioma "Greek" (griego clásico) además del inglés, si el instalador lo ofrece en la lista de idiomas adicionales.
2. Poppler: descarga el `.zip` desde [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) y descomprímelo en una carpeta fija, por ejemplo `C:\poppler` (Poppler para Windows no tiene instalador, es solo un `.zip` con los ejecutables dentro).

**macOS**, con [Homebrew](https://brew.sh) instalado:
```bash
brew install tesseract tesseract-lang poppler
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt install tesseract-ocr tesseract-ocr-grc poppler-utils
```
(`tesseract-ocr-grc` es el paquete de idioma griego; añade `tesseract-ocr-fra`, `tesseract-ocr-deu`, etc. según los idiomas que necesites.)

#### Paso 2: comprueba que el proyecto los encuentra automáticamente

`config.py` intenta localizarlos por su cuenta, sin que tengas que configurar nada, mirando: el `PATH` del sistema, y en macOS también las carpetas típicas de Homebrew/MacPorts. En la mayoría de los casos, con eso basta. Para comprobarlo, ejecuta:

```bash
python -c "import config; print(config.check_external_dependencies())"
```

- Si imprime `[]` (una lista vacía), todo está en orden y puedes pasar directamente a la sección "Uso" de más abajo.
- Si imprime uno o más mensajes de aviso, significa que no ha encontrado uno de los dos programas y te dice cómo instalarlo; si ya los tienes instalados pero en una ruta poco habitual, continúa con el Paso 3.

#### Paso 3: solo si el Paso 2 no los encontró, define la ruta a mano

Esto se hace con dos variables de entorno, **`TESSERACT_CMD`** (ruta al ejecutable de Tesseract) y **`POPPLER_PATH`** (ruta a la *carpeta* `bin` de Poppler, no al ejecutable). Hay que definirlas en la misma terminal donde vayas a ejecutar el script, cada vez que abras una terminal nueva (o añadirlas de forma permanente a tu perfil de shell, `.zshrc`/`.bashrc`/perfil de PowerShell, si no quieres repetir esto).

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
(ajusta la ruta a donde estén instalados realmente los programas; en un Mac con Homebrew suele ser `/opt/homebrew/bin` en chips Apple Silicon o `/usr/local/bin` en chips Intel).

Vuelve a ejecutar el comando de comprobación del Paso 2 para confirmar que ahora sí los encuentra.

---

**Con esto, la instalación está completa.** El siguiente paso es la sección "Uso" de abajo, donde se ejecuta la conversión de verdad.

## Uso

Documento completo:

```bash
python pdf_to_markdown.py "articulo.pdf" -o ./markdown --lang eng+grc
```

Solo un rango de páginas:

```bash
python pdf_to_markdown.py "libro.pdf" -o ./markdown --lang grc+eng+fra --pages 79-130
```

Con extracción de tablas (detecta automáticamente si el PDF es digital o escaneado):

```bash
python pdf_to_markdown.py "articulo.pdf" -o ./markdown --tables
```

Ver todas las opciones:

```bash
python pdf_to_markdown.py --help
```

El `.md` resultante se guarda en la carpeta indicada con `-o` y se abre automáticamente al terminar (usa `--no-open` para desactivar esto; en Linux/macOS se abre con `xdg-open`/`open` si están disponibles).

### Configuración de idiomas

El OCR usa `--lang eng+grc` (inglés + griego clásico) por defecto. Puedes añadir otros idiomas instalados en Tesseract (`fra`, `deu`, `ita`...) o dejar solo `grc` si el documento está enteramente en griego.

## Para usuarios sin conocimientos técnicos (sin Git, sin terminal)

Si vas a compartir esta herramienta con alguien que no sabe qué es Git ni una terminal, **no le mandes este repositorio para clonar**: mándale directamente un `.exe`/`.app` a través de la sección "Releases" de GitHub. Así su experiencia se reduce a: descargar un archivo, hacer doble clic, y usar la ventana.

### Qué tiene que hacer la persona que lo use (sin código)

1. Ve a la página de **Releases** del repositorio (enlace fijado en la barra lateral derecha de GitHub, o en `.../releases`).
2. Descarga el archivo según tu sistema, tu idioma preferido, y lo que necesites:
   - **Idioma:** cada aplicación existe en dos versiones independientes, "PDF a Markdown" (castellano) y "PDF to Markdown" (inglés). El comportamiento es idéntico, solo cambia el idioma de la ventana y los mensajes.
   - **Windows:** `.exe` (funciona en cualquier PC con Windows 10/11, no hay que elegir nada más aparte del idioma).
   - **macOS:** `.zip` con un `.app` dentro, pero aquí hay que elegir el correcto según el chip de tu Mac, **los dos no son intercambiables**:
     - **Apple Silicon** (M1, M2, M3, M4...): el archivo etiquetado **"macOS Apple Silicon"**.
     - **Intel** (cualquier Mac anterior a la transición de chip de finales de 2020): el archivo etiquetado **"macOS Intel"**.
     - ¿No sabes cuál tienes? Menú Apple (arriba a la izquierda) → "Acerca de este Mac": si pone "Chip" seguido de "Apple M...", tienes Apple Silicon; si pone "Procesador" seguido de "Intel Core...", tienes Intel.
     - Abrir el equivocado da un error de **"no es compatible con este Mac"** al hacer doble clic (no es un problema de permisos ni una descarga rota, es solo la arquitectura equivocada).
   - Cada combinación de idioma y sistema también viene en versión "solo texto" ("PDF a Markdown" / "PDF to Markdown") y versión "con tablas" ("PDF a Markdown (con tablas)" / "PDF to Markdown (with tables)").
3. Ábrelo:
   - **Windows:** doble clic. Probablemente aparezca un aviso de SmartScreen ("Windows ha protegido tu PC") porque el `.exe` no está firmado digitalmente; haz clic en **"Más información"** → **"Ejecutar de todas formas"**. Esto es normal en software de un solo desarrollador sin certificado de pago, no significa que el programa no sea seguro.
   - **macOS:** descomprime el `.zip`, y para el primer uso, clic derecho sobre el `.app` → "Abrir" (en vez de un doble clic normal), para saltarte el aviso de "desarrollador no verificado". Después de eso, un doble clic normal funciona bien.
4. Selecciona el PDF, la carpeta de salida, los idiomas, y pulsa "Convertir" ("Convert" en la versión inglesa).

### Tesseract y Poppler se instalan solos, sin terminal

Son programas externos de los que depende la app (no son librerías de Python, así que no se pueden incluir dentro del `.exe`/`.app`). Esto se aplica igual a las cuatro apps empaquetadas (las dos en castellano y las dos en inglés): comparten el mismo código de comprobación de dependencias, así que se comportan igual sea cual sea la que uses. La primera vez que falta alguno de los dos programas, se abre una ventana dentro de la aplicación que ofrece un único botón, en vez de fallar con un error críptico:

- **macOS:** **"🍺 Instalar automáticamente"** (o **"🍺 Instalar Homebrew y continuar"** en un Mac recién estrenado que todavía no tenga [Homebrew](https://brew.sh)). Un clic instala primero Homebrew si hace falta, y después Tesseract y Poppler a través de él, mostrando el progreso en directo en la misma ventana. Si hay que instalar Homebrew, macOS muestra una sola vez su propio diálogo nativo de contraseña de administrador, el mismo aviso estándar del sistema que usa cualquier instalador normal, no un comando de terminal disfrazado; todo lo que viene después se ejecuta sin más avisos.
- **Windows:** **"🪟 Instalar automáticamente"**, usando [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) (el gestor de paquetes integrado de Windows, presente por defecto en Windows 10/11 actualizados). Primero intenta una instalación solo para tu usuario (`--scope user`), que evita el aviso de permisos de administrador (UAC) para Poppler y el Visual C++ Redistributable. El instalador de Tesseract, sin embargo, solo está publicado para todo el equipo, así que para ese en concreto recurre a una instalación normal, que **sí** muestra el aviso estándar de UAC de Windows solo para ese paquete (basta con aceptarlo, no hay que escribir nada). Además de Tesseract y Poppler, también instala el **Visual C++ Redistributable** si falta: tanto Tesseract como Poppler lo necesitan solo para arrancar, y en un Windows realmente limpio (recién instalado, o una sandbox/VM desechable) muchas veces todavía no está, lo que produce un aviso del sistema, aparentemente sin relación, de **"No se encontró VCRUNTIME140.dll"** en vez del propio mensaje de error de Tesseract/Poppler. La mayoría de los equipos Windows normales, ya usados, ya lo tienen instalado como efecto secundario de otro software, así que en la práctica este paso suele no hacer nada.

Cuando termina la instalación, la ventana se cierra sola y la conversión arranca de inmediato, sin necesidad de volver a pulsar "Convertir".

Si el botón automático no está disponible por algún motivo (un Windows muy antiguo sin winget, o una restricción de red), la misma ventana recurre a las instrucciones manuales de más abajo.

<details>
<summary><strong>Windows: "Instalar automáticamente" sigue fallando aunque dice que Tesseract ya está instalado</strong></summary>

Esto puede pasar si un intento de instalación anterior, interrumpido, dejó una entrada rota: Windows (y winget) creen que Tesseract está instalado, pero los archivos del programa en realidad no están, así que ni volver a instalarlo ni desinstalarlo por los canales normales funciona. Síntomas: `winget uninstall UB-Mannheim.TesseractOCR` falla con `Application not found`, y "Aplicaciones instaladas" en Configuración muestra Tesseract, pero su propio desinstalador también falla con un error de "archivo no encontrado".

Para arreglarlo, elimina la entrada huérfana directamente, y deja que la app lo reinstale limpio:

1. Abre PowerShell **como Administrador**.
2. Comprueba que la entrada existe (esto solo lee, no cambia nada):
   ```powershell
   Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' | Where-Object { $_.GetValue('DisplayName') -like '*Tesseract*' } | Select-Object PSChildName
   ```
3. Elimínala (el nombre exacto de la clave normalmente es `Tesseract-OCR`, tal y como devuelve el comando anterior):
   ```powershell
   Remove-Item -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR' -Recurse
   ```
4. Cierra y vuelve a abrir la app, y prueba de nuevo "Instalar automáticamente".

</details>

<details>
<summary><strong>Instalación manual</strong> (solo hace falta si el botón automático de arriba no está disponible)</summary>

- **Windows:**
  1. Tesseract OCR: descarga el instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) y ejecútalo (deja las opciones por defecto; asegúrate de marcar el paquete de idioma griego, "Greek", si el instalador lo ofrece como opción).
  2. Poppler: descarga el `.zip` desde [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases), descomprímelo en, por ejemplo, `C:\poppler`.
  3. Si la aplicación no los encuentra automáticamente, define las variables de entorno `TESSERACT_CMD` y `POPPLER_PATH` (Panel de control → Sistema → Configuración avanzada → Variables de entorno) apuntando a la ruta del `.exe` de Tesseract y a la carpeta `bin` de Poppler respectivamente.
  4. Si en cambio te sale un aviso del sistema diciendo **"No se encontró VCRUNTIME140.dll"** (al ejecutar `pdfinfo.exe`/`pdftoppm.exe`/`tesseract.exe` directamente, o como parte de una conversión), es que falta el [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe), no un problema de instalación de Tesseract/Poppler: descarga y ejecuta ese instalador, y vuelve a intentarlo.

- **macOS:** abre la aplicación Terminal (viene con macOS) y ejecuta una vez:
  ```bash
  brew install tesseract tesseract-lang poppler
  ```
  (`tesseract-lang` incluye el paquete de griego clásico y otros idiomas; sin él, Tesseract solo reconoce inglés. Requiere tener [Homebrew](https://brew.sh) instalado primero.)

</details>

## Detección estricta de tablas

`PDF_a_Markdown_con_Tablas_GUI.py` (y `pdf_to_markdown.py --tables`) solo consideran que existe una tabla si se cumplen **todas** estas condiciones:

- La página contiene un pie de **tabla** explícito (no un pie de figura): "Table 1", "Tabla 1", "Tab. 1", "Cuadro 1", "Tableau 1"... (los pies de figura, "Figure"/"Fig."/"Abb.", quedan deliberadamente excluidos).
- La rejilla tiene al menos 3 filas y 2 columnas, con al menos un 75-80% de las filas compartiendo el mismo número de columnas.
- Al menos la mitad de las celdas contienen texto real tras el OCR (descarta cajas vacías o mal detectadas).
- En PDFs escaneados, además: se detectan al menos 4 líneas horizontales y 3 verticales (un simple marco decorativo con solo un borde exterior no cumple este mínimo), y la región debe cubrir al menos el 2% del área de la página.

Si un documento no tiene tablas de verdad, es normal y esperable que la aplicación indique "0 tablas encontradas": no fuerza encontrar algo que no está ahí.

## Cómo funciona

1. **Conversión a imágenes**: cada página del PDF (o el rango indicado) se convierte en una imagen a 300 ppp con `pdf2image`/Poppler.
2. **OCR página a página**: Tesseract extrae el texto de cada imagen.
3. **Extracción de tablas** (opcional, con `--tables`): `pdf_table_extractor.py` detecta si el PDF es digital o escaneado y extrae las tablas asociadas a un pie ("Tabla 1", "Table 2"...), insertándolas junto a su pie en el Markdown final.
4. **Corrección de errores**: `ocr_postprocess.fix_text()` limpia los errores típicos del OCR en griego clásico y en el texto académico circundante.
5. **Guardado**: el texto corregido de todas las páginas se une (con un separador `--- Página N ---` o `--- Page N ---` según el idioma) y se guarda como `.md` en UTF-8.

## Sobre el postprocesador de OCR

`ocr_postprocess.py` divide las reglas de corrección en tres grupos:

- `REGEX_RULES_GENERAL`: reglas genéricas y reutilizables (sigma final, ligaduras, guiones de fin de línea, notación epigráfica de Leiden...).
- `REGEX_RULES_CORPUS_SPECIFIC`: correcciones puntuales aprendidas de documentos concretos ya procesados (nombres propios, fragmentos de palabra muy específicos). No se aplican por defecto; actívalas con `fix_text(text, include_corpus_specific=True)` solo si estás reprocesando el mismo corpus de siempre.
- `REGEX_RULES_GREEK`: reglas específicas para bloques de texto griego.

## Ejecutar los tests

El proyecto tiene una batería de tests automatizados (`pytest`) que cubre las reglas de postprocesado de OCR, la detección estricta de tablas, la resolución de dependencias, y el análisis de argumentos de la línea de comandos:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

La mayoría de los tests son tests unitarios puros y se ejecutan al instante sin dependencias externas. Unos pocos tests de extremo a extremo ponen a prueba el pipeline completo de OCR contra un PDF de muestra pequeño (`tests/fixtures/sample_with_table.pdf`) y se omiten automáticamente si Tesseract o Poppler no están instalados en la máquina donde se ejecutan los tests.

Los tests se ejecutan automáticamente en cada `push` y pull request mediante GitHub Actions (ver `.github/workflows/tests.yml`), en Linux, macOS y Windows.

## Limitaciones conocidas

- La extracción de tablas en PDFs escaneados asume tablas con bordes explícitos (líneas horizontales y verticales visibles); las tablas sin bordes no se detectan.
- `os.startfile()` (apertura automática del archivo `.md`) es específico de Windows; en otros sistemas se usa `open`/`xdg-open` como alternativa razonable.
