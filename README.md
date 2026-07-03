# PDF-TO-MARKDOWN-CLASSIC-GREEK

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21130682.svg)](https://doi.org/10.5281/zenodo.21130682)

Converts a PDF containing Classical Greek text (and/or English, French, Italian, etc.) into a Markdown (`.md`) file using optical character recognition (OCR), then corrects the errors typical of Greek OCR.

> **No computing background?** Skip everything below (cloning the repository, terminal, Python...) and go directly to the **["For non-technical users (no Git, no terminal)"](#for-non-technical-users-no-git-no-terminal)** section, which explains how to download and use the application with a double-click, no code involved.
>
> That said: **this project also depends on Tesseract OCR and Poppler**, two external programs (not Python libraries, so they are not bundled inside the repository or the `.exe`/`.app`). If you run the code from source, you need to install them yourself (see "Prerequisites" below). If you use the double-click application instead, it can install both for you automatically, with a single click and no terminal involved, see the "For non-technical users" section for details.

## How to cite this software

If you use this tool in your research, please cite it as:

> Candel Lozano, C. (2026). *PDF-TO-MARKDOWN-CLASSIC-GREEK: OCR-based PDF-to-Markdown conversion with automatic post-processing for Classical Greek* (v1.10) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21130682

In BibTeX format:

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

Full metadata (author, license, keywords) is also available in the [`CITATION.cff`](./CITATION.cff) file of this repository, and GitHub displays it directly with the **"Cite this repository"** button in the sidebar.

## Why Markdown and not another format

A PDF is, essentially, a fixed image: an AI (Claude, ChatGPT, Gemini...) cannot read its content directly. The text has to be extracted first and saved in a format the AI can understand well.

- **Plain text** (no binary formatting layers like `.docx` or `.pdf`), read from start to finish effortlessly.
- **Preserves structure**: headings, lists, bold text, etc. are marked with simple symbols, so the AI can tell the hierarchy apart instead of seeing a mass of flat text.
- **Claude's native format**: the exchange between the text and the AI is more direct and precise.
- **Very small footprint**: a 10 MB PDF can end up as just a few KB, leaving more room in the context window.
- **Universal and durable**: any text editor can open it, with no dependency on licenses or software versions.

Typical workflow:

```
PDF (original) → .md (this script) → paste/upload to Claude → summarize, translate, analyze, extract data...
```

## Project structure

| File | Purpose |
| --- | --- |
| `pdf_to_markdown.py` | Main script (CLI). Converts the whole PDF, a page range, and optionally extracts tables. |
| `PDF_a_Markdown_GUI.py` | Desktop application (no terminal), text only. |
| `PDF_a_Markdown_con_Tablas_GUI.py` | Desktop application (no terminal), text + strict table extraction. |
| `gui_common.py` | Conversion engine and components shared by the two desktop applications. |
| `tema_calido.json` | Visual theme (amber/brown tones) for the desktop applications. |
| `ocr_postprocess.py` | Corrects errors typical of OCR on Classical Greek and the surrounding multilingual academic text. |
| `pdf_table_extractor.py` | Extracts tables from digital PDFs (with `pdfplumber`) or scanned PDFs (with OpenCV + Tesseract), with strict detection. |
| `config.py` | Centralized configuration of Tesseract and Poppler paths (via environment variables), plus automatic installation via Homebrew (macOS) and winget (Windows). |
| `tests/` | Automated `pytest` test suite (unit tests + a small end-to-end fixture). |

## Prerequisites

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (with the language packs you need, e.g. `grc` for Classical Greek)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) (on Windows; on Linux/macOS installing it via the system package manager is usually enough)

### Clone the repository

Open a terminal (on Windows, Git Bash; on Linux/macOS, the regular Terminal) and run, one at a time:

```bash
git clone https://github.com/candellozanocarlos/PDF-TO-MARKDOWN-CLASSIC-GREEK.git
```

This creates a new folder called `PDF-TO-MARKDOWN-CLASSIC-GREEK` with a full copy of the repository. Enter it:

```bash
cd PDF-TO-MARKDOWN-CLASSIC-GREEK
```

All the commands in the sections below (`pip install`, `python pdf_to_markdown.py`, etc.) are run **from inside this folder**. If at any point a command gives "No such file or directory" or "command not found", the first thing to check is that you are still inside `PDF-TO-MARKDOWN-CLASSIC-GREEK` (with `pwd` on Linux/macOS, or simply by looking at the path shown next to the `$` symbol in Git Bash).

If later on you want to update your local copy with the latest changes pushed to the repository, do so with:

```bash
git pull
```

### Install the Python dependencies

```bash
pip install -r requirements.txt
```

### Install and configure Tesseract and Poppler

The project needs two external programs that are **not Python libraries** (which is why `pip install -r requirements.txt` does not install them):

- **Tesseract OCR**: the engine that "reads" the text inside the image of each PDF page. Without it, no conversion is possible.
- **Poppler**: the library that converts each PDF page into an image before handing it to Tesseract (used under the hood by `pdf2image`).

#### Step 1 — Install them

**Windows:**
1. Tesseract: download the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and run it. During installation, check the "Greek" (Classical Greek) language pack in addition to English, if the installer offers it in the additional-languages list.
2. Poppler: download the `.zip` from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) and unzip it into a fixed folder, e.g. `C:\poppler` (Poppler for Windows has no installer, it is just a `.zip` with the executables inside).

**macOS**, with [Homebrew](https://brew.sh) installed:
```bash
brew install tesseract tesseract-lang poppler
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt install tesseract-ocr tesseract-ocr-grc poppler-utils
```
(`tesseract-ocr-grc` is the Greek language pack; add `tesseract-ocr-fra`, `tesseract-ocr-deu`, etc. depending on the languages you need.)

#### Step 2 — Check that the project finds them automatically

`config.py` tries to locate them on its own, without you having to configure anything, by looking at: the system `PATH`, and on macOS also the typical Homebrew/MacPorts directories. In most cases that is enough. To check, run:

```bash
python -c "import config; print(config.check_external_dependencies())"
```

- If it prints `[]` (an empty list), everything is fine and you can jump straight to the "Usage" section below.
- If it prints one or more warning messages, it means it could not find one of the two programs and tells you how to install it; if you already have them installed but in an unusual path, continue with Step 3.

#### Step 3 — Only if Step 2 did not find them: set the path manually

This is done with two environment variables, **`TESSERACT_CMD`** (path to the Tesseract executable) and **`POPPLER_PATH`** (path to Poppler's `bin` *folder*, not the executable). They need to be set in the same terminal where you are going to run the script, every time you open a new terminal (or add them permanently to your shell profile, `.zshrc`/`.bashrc`/PowerShell profile, if you do not want to repeat this).

**Windows (Git Bash or PowerShell):**
```bash
export TESSERACT_CMD="/c/Program Files/Tesseract-OCR/tesseract.exe"
export POPPLER_PATH="/c/poppler/Library/bin"
```
or, in PowerShell:
```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:POPPLER_PATH  = "C:\poppler\Library\bin"
```

**Linux / macOS:**
```bash
export TESSERACT_CMD=/usr/bin/tesseract
export POPPLER_PATH=/usr/bin
```
(adjust the path to wherever the programs are actually installed; on a Mac with Homebrew it is usually `/opt/homebrew/bin` on Apple silicon or `/usr/local/bin` on Intel chips).

Run the Step 2 check command again to confirm it now finds them.

---

**With this, installation is complete.** The next step is the "Usage" section below, where the actual conversion is run.

## Usage

Full document:

```bash
python pdf_to_markdown.py "article.pdf" -o ./markdown --lang eng+grc
```

Only a page range:

```bash
python pdf_to_markdown.py "book.pdf" -o ./markdown --lang grc+eng+fra --pages 79-130
```

With table extraction (automatically detects whether the PDF is digital or scanned):

```bash
python pdf_to_markdown.py "article.pdf" -o ./markdown --tables
```

See all options:

```bash
python pdf_to_markdown.py --help
```

The resulting `.md` is saved in the output folder given with `-o` and opens automatically when done (use `--no-open` to disable this; on Linux/macOS it opens with `xdg-open`/`open` if available).

### Language configuration

OCR uses `--lang eng+grc` (English + Classical Greek) by default. You can add other languages installed in Tesseract (`fra`, `deu`, `ita`...) or leave only `grc` if the document is entirely in Greek.

## For non-technical users (no Git, no terminal)

If you are going to share this tool with someone who does not know what Git or a terminal is, **do not send them this repository to clone**: send them a `.exe`/`.app` directly through GitHub's "Releases" section instead. That way their experience boils down to: download a file, double-click it, and use the window.

### What the person using it has to do (no code)

1. Go to the repository's **Releases** page (link pinned in GitHub's right-hand sidebar, or at `.../releases`).
2. Download the file matching your system and what you need:
   - **Windows:** `.exe` (works on any Windows 10/11 PC, no need to pick anything else).
   - **macOS:** `.zip` containing an `.app`, but here you must pick the right one for your Mac's chip, **the two are not interchangeable**:
     - **Apple Silicon** (M1, M2, M3, M4...): the file labeled **"macOS Apple Silicon"**.
     - **Intel** (any Mac from before the chip transition in late 2020): the file labeled **"macOS Intel"**.
     - Not sure which one you have? Apple menu (top-left corner) → "About This Mac": if it says "Chip" followed by "Apple M...", you have Apple Silicon; if it says "Processor" followed by "Intel Core...", you have Intel.
     - Opening the wrong one gives a **"is not compatible with this Mac"** error when double-clicking (not a permissions issue, not a broken download, just the wrong architecture).
   - Each of the two macOS builds also comes in a "text only" version ("PDF a Markdown") and a "with tables" version ("PDF a Markdown (con tablas)"), same as on Windows.
3. Open it:
   - **Windows:** double-click. A SmartScreen warning ("Windows protected your PC") will probably appear because the `.exe` is not digitally signed; click **"More info"** → **"Run anyway"**. This is normal for software from a single developer without a paid certificate, it does not mean the program is unsafe.
   - **macOS:** unzip the `.zip`, and for the first use, right-click the `.app` → "Open" (instead of a normal double-click), to skip the "unverified developer" warning. After that, a normal double-click works fine.
4. Select the PDF, the output folder, the languages, and click "Convertir" ("Convert").

### Tesseract and Poppler install themselves, no terminal needed

These are external programs the app depends on (not Python libraries, so they cannot be bundled inside the `.exe`/`.app` itself). The first time either one is missing, a window opens inside the application offering a single button, instead of failing with a cryptic error:

- **macOS:** **"🍺 Instalar automáticamente"** (or **"🍺 Instalar Homebrew y continuar"** on a brand-new Mac that does not have [Homebrew](https://brew.sh) yet). One click installs Homebrew first if needed, then Tesseract and Poppler through it, showing the progress live in the same window. If Homebrew itself has to be installed, macOS shows its own native administrator-password dialog once, the standard system prompt used by any regular installer, not a disguised terminal command; everything after that runs without further prompts.
- **Windows:** **"🪟 Instalar automáticamente"**, using [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) (Windows' built-in package manager, present by default on Windows 10/11 kept up to date). It tries a per-user install first (`--scope user`), which avoids the UAC administrator prompt for Poppler and the Visual C++ Redistributable. Tesseract's own installer, however, is only published machine-wide, so for that one specifically it falls back to a normal install, which **does** show the standard Windows UAC prompt just for that package (accepting it is enough, no typing involved). Besides Tesseract and Poppler, it also installs the **Visual C++ Redistributable** if missing: both Tesseract and Poppler need it just to start, and on a truly clean Windows (freshly installed, or a disposable sandbox/VM) it is often not there yet, producing an unrelated-looking **"VCRUNTIME140.dll was not found"** system dialog instead of Tesseract/Poppler's own error message. Most regular, already-used Windows machines already have it installed as a side effect of other software, so in practice this step is usually a no-op.

Once installation finishes, the window closes on its own and the conversion starts immediately, no need to press "Convert" again.

If the automatic button is not available for some reason (a very old Windows without winget, or a network restriction), the same window falls back to the manual instructions below.

<details>
<summary><strong>Manual installation</strong> (only needed if the automatic button above is unavailable)</summary>

- **Windows:**
  1. Tesseract OCR: download the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and run it (leave the default options; make sure to check the Greek language pack, "Greek", if the installer offers it as an option).
  2. Poppler: download the `.zip` from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases), unzip it into, e.g., `C:\poppler`.
  3. If the application does not find them automatically, set the `TESSERACT_CMD` and `POPPLER_PATH` environment variables (Control Panel → System → Advanced settings → Environment Variables) pointing to Tesseract's `.exe` path and to Poppler's `bin` folder respectively.
  4. If, instead, you get a system dialog saying **"VCRUNTIME140.dll was not found"** (when running `pdfinfo.exe`/`pdftoppm.exe`/`tesseract.exe` directly, or as part of a conversion), that is a missing [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe), not a Tesseract/Poppler installation problem: download and run that installer, then try again.

- **macOS:** open the Terminal app (comes with macOS) and run once:
  ```bash
  brew install tesseract tesseract-lang poppler
  ```
  (`tesseract-lang` includes the Classical Greek package and other languages; without it, Tesseract only recognizes English. Requires [Homebrew](https://brew.sh) installed first.)

</details>

## Strict table detection

`PDF_a_Markdown_con_Tablas_GUI.py` (and `pdf_to_markdown.py --tables`) only consider that a table exists if **all** of the following hold:

- The page contains an explicit **table** caption (not a figure caption): "Table 1", "Tabla 1", "Tab. 1", "Cuadro 1", "Tableau 1"... (figure captions, "Figure"/"Fig."/"Abb.", are deliberately excluded).
- The grid has at least 3 rows and 2 columns, with at least 75-80% of rows sharing the same number of columns.
- At least half of the cells contain real text after OCR (discards empty or misdetected boxes).
- On scanned PDFs, additionally: at least 4 horizontal and 3 vertical lines detected (a plain decorative frame with only an outer border does not meet this minimum), and the region must cover at least 2% of the page area.

If a document has no real tables, it is normal and expected for the application to report "0 tablas encontradas" ("0 tables found"): it does not force finding something that is not there.

## How it works

1. **Conversion to images**: each page of the PDF (or the given range) is converted into an image at 300 dpi with `pdf2image`/Poppler.
2. **Page-by-page OCR**: Tesseract extracts the text from each image.
3. **Table extraction** (optional, with `--tables`): `pdf_table_extractor.py` detects whether the PDF is digital or scanned and extracts the tables associated with a caption ("Tabla 1", "Table 2"...), inserting them next to their caption in the final Markdown.
4. **Error correction**: `ocr_postprocess.fix_text()` cleans up errors typical of OCR on Classical Greek and the surrounding academic text.
5. **Saving**: the corrected text of all pages is joined (with a `--- Page N ---` separator) and saved as UTF-8 `.md`.

## About the OCR post-processor

`ocr_postprocess.py` splits the correction rules into three groups:

- `REGEX_RULES_GENERAL`: generic, reusable rules (final sigma, ligatures, end-of-line hyphens, Leiden epigraphic notation...).
- `REGEX_RULES_CORPUS_SPECIFIC`: ad hoc corrections learned from specific documents already processed (proper nouns, very specific word fragments). Not applied by default; enable them with `fix_text(text, include_corpus_specific=True)` only if you are reprocessing the same corpus as always.
- `REGEX_RULES_GREEK`: rules specific to Greek text blocks.

## Running the tests

The project has an automated test suite (`pytest`) covering the OCR post-processing rules, strict table detection, dependency resolution, and CLI argument parsing:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Most tests are pure unit tests and run instantly with no external dependencies. A few end-to-end tests exercise the full OCR pipeline against a small sample PDF (`tests/fixtures/sample_with_table.pdf`) and are automatically skipped if Tesseract or Poppler are not installed on the machine running the tests.

Tests run automatically on every push and pull request via GitHub Actions (see `.github/workflows/tests.yml`), on Linux, macOS, and Windows.

## Known limitations

- Table extraction on scanned PDFs assumes tables with explicit borders (visible horizontal and vertical lines); borderless tables are not detected.
- `os.startfile()` (automatic opening of the `.md` file) is Windows-specific; on other systems `open`/`xdg-open` is used as a best-effort alternative.
