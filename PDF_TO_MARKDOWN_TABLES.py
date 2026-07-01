import pytesseract
from pdf2image import convert_from_path
import os
from ocr_postprocess_mejorado import corregir_texto
from pdf_table_extractor import extraer_tablas, CAPTION_RE


def insertar_tablas_junto_a_caption(texto: str, tablas_md: list) -> str:
    """Inserta cada tabla markdown justo después de su caption en el texto OCR.
    Si no hay ningún caption visible en el texto, no se inserta nada."""
    if not tablas_md:
        return texto
    matches = list(CAPTION_RE.finditer(texto))
    if not matches:
        return texto
    partes = []
    prev_end = 0
    for i, m in enumerate(matches):
        partes.append(texto[prev_end:m.end()])
        if i < len(tablas_md):
            partes.append(f"\n\n{tablas_md[i]}\n")
        prev_end = m.end()
    partes.append(texto[prev_end:])
    return "".join(partes)


# Rutas
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\Library\bin"

PDF_DIR    = r"C:\Users\Carlos Candel\OneDrive - UVa\PYTHON"
OUTPUT_DIR = r"C:\Users\Carlos Candel\OneDrive - UVa\MARKDOWN"
PDF_NAME   = "Graeco_Anatolian_Pamphylia_A_Network_Ana.pdf"
LANG       = "eng+grc"
TIPO_PDF   = "digital"   # "digital" (texto seleccionable) o "escaneado" (imágenes)

os.makedirs(OUTPUT_DIR, exist_ok=True)

pdf_path        = os.path.join(PDF_DIR, PDF_NAME)
output_filename = os.path.splitext(PDF_NAME)[0] + "_tablas.md"
output_path     = os.path.join(OUTPUT_DIR, output_filename)

# Convertir PDF a imágenes
print("Convirtiendo PDF a imágenes...")
pages = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)

# Extraer tablas (auto-detecta si el PDF es digital o escaneado)
print("Extrayendo tablas...")
tablas_por_pagina = extraer_tablas(
    pdf_path,
    tipo=TIPO_PDF,
    imagenes=pages,
    lang=LANG,
    aplicar_postproc=True,
)

# OCR página por página
print(f"Procesando {len(pages)} páginas...")
texto_completo = ""

for i, page in enumerate(pages):
    num_pagina = i + 1
    print(f"  Página {num_pagina}/{len(pages)}...")
    texto_bruto   = pytesseract.image_to_string(page, lang=LANG, config="--psm 3")
    texto_corregido = corregir_texto(texto_bruto, verbose=True)

    if num_pagina in tablas_por_pagina:
        texto_corregido = insertar_tablas_junto_a_caption(
            texto_corregido, tablas_por_pagina[num_pagina]
        )

    texto_completo += f"\n\n--- Página {num_pagina} ---\n\n{texto_corregido}"

# Guardar
with open(output_path, "w", encoding="utf-8") as f:
    f.write(texto_completo)

print(f"Listo. Archivo guardado en:\n{output_path}")
os.startfile(output_path)
