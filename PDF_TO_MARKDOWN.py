import pytesseract
from pdf2image import convert_from_path
import os
from ocr_postprocess_mejorado import corregir_texto


# Rutas
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\Library\bin"

PDF_DIR    = r"C:\Users\Carlos Candel\OneDrive - UVa\PYTHON"
OUTPUT_DIR = r"C:\Users\Carlos Candel\OneDrive - UVa\MARKDOWN"
PDF_NAME   = "Dodona_e_il_commercio_nellAdriatico_a_pr.pdf"
LANG       = "ita+grc"

os.makedirs(OUTPUT_DIR, exist_ok=True)

pdf_path        = os.path.join(PDF_DIR, PDF_NAME)
output_filename = os.path.splitext(PDF_NAME)[0] + ".md"
output_path     = os.path.join(OUTPUT_DIR, output_filename)

# Convertir PDF a imágenes
print("Convirtiendo PDF a imágenes...")
pages = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)


# OCR página por página
print(f"Procesando {len(pages)} páginas...")
texto_completo = ""

for i, page in enumerate(pages):
    num_pagina = i + 1
    print(f"  Página {num_pagina}/{len(pages)}...")
    texto_bruto     = pytesseract.image_to_string(page, lang=LANG, config="--psm 3")
    texto_corregido = corregir_texto(texto_bruto, verbose=True)
    texto_completo += f"\n\n--- Página {num_pagina} ---\n\n{texto_corregido}"

# Guardar
with open(output_path, "w", encoding="utf-8") as f:
    f.write(texto_completo)

print(f"Listo. Archivo guardado en:\n{output_path}")
os.startfile(output_path)
