import pytesseract
from pdf2image import convert_from_bytes
import os
from ocr_postprocess_mejorado import corregir_texto

# Rutas
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\Library\bin"

PDF_DIR    = r"C:\Users\Carlos Candel\OneDrive - UVa\PYTHON" 
OUTPUT_DIR = r"C:\Users\Carlos Candel\OneDrive - UVa\MARKDOWN"
PDF_NAME   = "Δωδώνη. Οι ερωτήσεις των χρησμών. Νέες προσεγγίσεις στα χρηστήρια ελάσματα.pdf"

x
PAGINA_INICIO = 79
PAGINA_FIN    = 130

os.makedirs(OUTPUT_DIR, exist_ok=True)

output_filename = os.path.splitext(PDF_NAME)[0] + f"_pp{PAGINA_INICIO}-{PAGINA_FIN}.md"
output_path     = os.path.join(OUTPUT_DIR, output_filename)
pdf_path        = os.path.join(PDF_DIR, PDF_NAME)

print("Leyendo PDF...")
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

print(f"Convirtiendo páginas {PAGINA_INICIO}-{PAGINA_FIN} a imágenes...")
pages = convert_from_bytes(
    pdf_bytes,
    dpi=300,
    poppler_path=POPPLER_PATH,
    first_page=PAGINA_INICIO,
    last_page=PAGINA_FIN
)

print(f"Procesando {len(pages)} páginas...")
texto_completo = ""

for i, page in enumerate(pages):
    num_pagina = PAGINA_INICIO + i
    print(f"  Página {num_pagina}/{PAGINA_FIN}...")
    texto_bruto  = pytesseract.image_to_string(page, lang="grc+eng+fra")
    texto_limpio = corregir_texto(texto_bruto, verbose=True)
    texto_completo += f"\n\n--- Página {num_pagina} ---\n\n{texto_limpio}"

with open(output_path, "w", encoding="utf-8") as f:
    f.write(texto_completo)

print(f"Listo. Archivo guardado en:\n{output_path}")
