"""
pdf_table_extractor.py
----------------------
Extracción de tablas para dos tipos de PDF:
  - Digital (texto seleccionable): pdfplumber detecta la estructura directamente.
  - Escaneado (imagen): OpenCV localiza las celdas, Tesseract las lee una a una.

Uso rápido:
    from pdf_table_extractor import extraer_tablas, detectar_tipo_pdf

    tipo = detectar_tipo_pdf("articulo.pdf")            # "digital" o "escaneado"
    tablas = extraer_tablas("articulo.pdf", imagenes)   # {num_pag: [md, ...]}
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pdfplumber
import pytesseract
from PIL import Image

import config  # noqa: F401  (aplica TESSERACT_CMD al importarse; evita duplicar la ruta aquí)
from ocr_postprocess_mejorado import corregir_texto

# ---------------------------------------------------------------------------
# Patrón de pie de tabla / figura (multilingüe)
# Solo se extrae la tabla si la página contiene uno de estos pies.
# ---------------------------------------------------------------------------
CAPTION_RE = re.compile(
    r"^\s*(?:Table|Tab\.?|Figure|Fig\.?|Tabla|Cuadro|Abbildung|Abb\.?|Tableau|Tav\.?)\s*\.?\s*\d+",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Utilidad compartida: lista-de-listas → tabla Markdown
# ---------------------------------------------------------------------------

def _tabla_a_markdown(filas: list[list[str]]) -> str:
    if not filas:
        return ""
    # Normalizar celdas
    filas = [[str(c or "").strip() for c in fila] for fila in filas]
    ncols = max(len(f) for f in filas)
    filas = [f + [""] * (ncols - len(f)) for f in filas]

    anchos = [max(len(f[c]) for f in filas) or 1 for c in range(ncols)]

    def _fila_md(fila: list[str]) -> str:
        return "| " + " | ".join(c.ljust(anchos[i]) for i, c in enumerate(fila)) + " |"

    sep = "| " + " | ".join("-" * a for a in anchos) + " |"
    return "\n".join([_fila_md(filas[0]), sep] + [_fila_md(f) for f in filas[1:]])


# ---------------------------------------------------------------------------
# Detección automática del tipo de PDF
# ---------------------------------------------------------------------------

def detectar_tipo_pdf(pdf_path: str, umbral_chars: int = 80) -> str:
    """
    Lee el texto de la primera página con pdfplumber.
    Si obtiene al menos `umbral_chars` caracteres, el PDF es digital;
    si no, es escaneado (las páginas son imágenes).
    """
    with pdfplumber.open(pdf_path) as pdf:
        texto = pdf.pages[0].extract_text() or ""
    tipo = "digital" if len(texto.strip()) >= umbral_chars else "escaneado"
    print(f"[table_extractor] Tipo detectado: {tipo}  "
          f"({len(texto.strip())} caracteres en pág. 1)")
    return tipo


# ===========================================================================
# FLUJO 1 — PDF DIGITAL (pdfplumber)
# ===========================================================================

def extraer_tablas_digital(
    pdf_path: str,
    paginas: Optional[list[int]] = None,
    aplicar_postproc: bool = True,
) -> dict[int, list[str]]:
    """
    Extrae tablas de un PDF con texto seleccionable.

    Parámetros
    ----------
    pdf_path        : ruta al PDF.
    paginas         : lista de índices 0-based; None = todo el documento.
    aplicar_postproc: pasa cada celda por corregir_texto().

    Devuelve
    --------
    {num_pagina_1based: [tabla_markdown, ...]}
    """
    resultado: dict[int, list[str]] = {}

    # Bordes explícitos — única estrategia activa (la alineación de texto generaba
    # demasiados falsos positivos en listas, bibliografías y texto en columnas).
    cfg_lines = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 5,
        "join_tolerance": 3,
        "edge_min_length": 30,
        "min_words_vertical": 1,
        "min_words_horizontal": 1,
    }

    def _es_tabla_real(tabla: list) -> bool:
        """Descarta estructuras de < 3 filas, 1 columna o con columnas irregulares."""
        if not tabla or len(tabla) < 3:
            return False
        n_cols = [len(fila) for fila in tabla]
        if max(n_cols) < 2:
            return False
        modo = max(set(n_cols), key=n_cols.count)
        return sum(1 for n in n_cols if n == modo) >= max(2, len(tabla) * 0.6)

    with pdfplumber.open(pdf_path) as pdf:
        indices = list(paginas) if paginas is not None else list(range(len(pdf.pages)))

        # Pre-escaneo: páginas con caption propio + página siguiente
        # (el caption puede estar encima de la tabla, al final de la pág anterior)
        con_tabla: set[int] = set()
        for i in indices:
            texto = pdf.pages[i].extract_text() or ""
            if CAPTION_RE.search(texto):
                con_tabla.add(i)        # caption en la misma página
                con_tabla.add(i + 1)    # tabla puede empezar en la siguiente

        for i in indices:
            if i not in con_tabla:
                continue

            pagina = pdf.pages[i]
            tablas = pagina.extract_tables(table_settings=cfg_lines)

            mds = []
            for tabla in tablas:
                if not _es_tabla_real(tabla):
                    continue
                if aplicar_postproc:
                    tabla = [
                        [corregir_texto(c) if c else "" for c in fila]
                        for fila in tabla
                    ]
                md = _tabla_a_markdown(tabla)
                if md:
                    mds.append(md)

            if mds:
                num_pagina = i + 1
                resultado[num_pagina] = mds
                print(f"[table_extractor] Pág. {num_pagina}: {len(mds)} tabla(s) extraída(s)")

    return resultado


# ===========================================================================
# FLUJO 2 — PDF ESCANEADO (OpenCV + Tesseract)
# ===========================================================================

# ── 2a. Pre-procesamiento de imagen ─────────────────────────────────────────

def _preprocesar(img_gray: np.ndarray) -> np.ndarray:
    """Binarización Otsu + eliminación de ruido puntual."""
    _, bin_inv = cv2.threshold(img_gray, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    limpia = cv2.morphologyEx(bin_inv, cv2.MORPH_OPEN, kernel)
    return cv2.bitwise_not(limpia)


# ── 2b. Detección de la región de tabla ─────────────────────────────────────

def _separar_lineas(img_gray: np.ndarray):
    """
    Devuelve (lineas_h, lineas_v) como máscaras binarias.
    Kernels grandes (≥ 1/4 de la dimensión) para que solo pasen
    los bordes reales de tabla y no subrayados ni separadores cortos.
    """
    h, w = img_gray.shape
    _, binaria = cv2.threshold(img_gray, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 4, 60), 1))
    lineas_h = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, k_h)

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 4, 60)))
    lineas_v = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, k_v)

    return lineas_h, lineas_v


def _bbox_tabla(img_gray: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """
    Devuelve (x, y, w, h) de la tabla, o None si no hay tabla.

    Estrategia: una tabla real tiene intersecciones entre líneas horizontales
    y verticales.  Buscamos el contorno del área de líneas que contiene más
    intersecciones (≥ 4, es decir al menos una celda 2×2).
    """
    lineas_h, lineas_v = _separar_lineas(img_gray)

    # Píxeles en los que coinciden línea horizontal Y vertical → intersecciones
    intersecciones = cv2.bitwise_and(lineas_h, lineas_v)
    if cv2.countNonZero(intersecciones) < 4:
        return None

    # Máscara completa de líneas; dilatar para conectar los bordes de cada celda
    mascara = cv2.add(lineas_h, lineas_v)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mascara = cv2.dilate(mascara, k, iterations=3)

    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None

    # Escoger el contorno cuyo interior contiene más intersecciones
    mejor_bbox = None
    mejor_n = 0
    for c in contornos:
        x, y, cw, ch = cv2.boundingRect(c)
        n = cv2.countNonZero(intersecciones[y:y+ch, x:x+cw])
        if n > mejor_n:
            mejor_n = n
            mejor_bbox = (x, y, cw, ch)

    return mejor_bbox if mejor_n >= 4 else None


# ── 2c. Detección y agrupación de celdas ────────────────────────────────────

def _detectar_celdas(roi: np.ndarray) -> list[tuple[int, int, int, int]]:
    """
    Dentro del ROI de la tabla detecta cada celda como espacio entre líneas.
    Usa jerarquía CCOMP para descartar el contorno padre (toda la imagen).
    """
    h, w = roi.shape
    lineas_h, lineas_v = _separar_lineas(roi)
    mascara = cv2.add(lineas_h, lineas_v)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mascara = cv2.dilate(mascara, k, iterations=2)
    interior = cv2.bitwise_not(mascara)

    contornos, jerarquia = cv2.findContours(interior, cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_SIMPLE)
    area_roi = h * w
    celdas = []
    for i, c in enumerate(contornos):
        # CCOMP: jerarquia[0][i][3] == -1 → contorno sin padre (es la imagen entera)
        if jerarquia is not None and jerarquia[0][i][3] == -1:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        area_rel = (cw * ch) / area_roi
        if 0.003 <= area_rel <= 0.5 and cw < w * 0.97 and ch < h * 0.97:
            celdas.append((x, y, cw, ch))

    celdas.sort(key=lambda c: (c[1], c[0]))
    return celdas


def _agrupar_filas(celdas: list[tuple], tolerancia_pct: float = 0.025,
                   alto_roi: int = 100) -> list[list[tuple]]:
    """Agrupa celdas en filas usando tolerancia relativa al alto del ROI."""
    if not celdas:
        return []
    tolerancia = max(int(alto_roi * tolerancia_pct), 8)
    filas: list[list[tuple]] = []
    fila_actual = [celdas[0]]
    y_ref = celdas[0][1]

    for celda in celdas[1:]:
        if abs(celda[1] - y_ref) <= tolerancia:
            fila_actual.append(celda)
        else:
            filas.append(sorted(fila_actual, key=lambda c: c[0]))
            fila_actual = [celda]
            y_ref = celda[1]
    filas.append(sorted(fila_actual, key=lambda c: c[0]))
    return filas


def _es_grid_valido(filas: list[list]) -> bool:
    """
    Verifica que las filas formen un grid coherente:
    - Al menos 2 filas y 2 columnas.
    - ≥ 70 % de las filas tienen el mismo número de columnas.
    """
    if len(filas) < 2:
        return False
    n_cols = [len(f) for f in filas]
    if max(n_cols) < 2:
        return False
    modo = max(set(n_cols), key=n_cols.count)
    return sum(1 for n in n_cols if n == modo) >= max(2, len(filas) * 0.7)


# ── 2d. OCR de celda individual ──────────────────────────────────────────────

def _ocr_celda(recorte: np.ndarray, lang: str) -> str:
    """OCR de una celda con PSM 7 (una línea) o PSM 6 si es multilinea."""
    alto = recorte.shape[0]
    # Padding para evitar que Tesseract corte caracteres del borde
    padded = cv2.copyMakeBorder(recorte, 6, 6, 6, 6,
                                cv2.BORDER_CONSTANT, value=255)
    pil_img = Image.fromarray(padded)

    psm = "7" if alto < 60 else "6"
    config = f"--psm {psm} -c preserve_interword_spaces=1"
    texto = pytesseract.image_to_string(pil_img, lang=lang, config=config)
    return texto.strip()


# ── 2e. Pipeline completo para una imagen ────────────────────────────────────

def extraer_tabla_de_imagen(
    imagen_pil: Image.Image,
    lang: str = "grc+eng",
    aplicar_postproc: bool = True,
    texto_pagina_anterior: Optional[str] = None,
    _texto_pagina: Optional[str] = None,
) -> Optional[str]:
    """
    Detecta y extrae la tabla de una imagen PIL (una página escaneada).

    Devuelve la tabla en formato Markdown, o None si no se detecta tabla.
    `_texto_pagina` permite reutilizar un OCR ya realizado externamente.
    """
    # Paso 0: verificar caption (en esta página o en la anterior).
    texto_pagina = _texto_pagina or pytesseract.image_to_string(
        imagen_pil, lang=lang, config="--psm 3"
    )
    tiene_caption = CAPTION_RE.search(texto_pagina) or (
        texto_pagina_anterior and CAPTION_RE.search(texto_pagina_anterior)
    )
    if not tiene_caption:
        return None

    img_gray = np.array(imagen_pil.convert("L"))
    img_proc = _preprocesar(img_gray)

    bbox = _bbox_tabla(img_proc)
    if bbox is None:
        return None

    x, y, w, h = bbox
    roi = img_proc[y:y+h, x:x+w]

    celdas = _detectar_celdas(roi)
    if len(celdas) < 4:
        return None

    filas = _agrupar_filas(celdas, alto_roi=h)
    if not _es_grid_valido(filas):
        return None

    datos: list[list[str]] = []
    for fila in filas:
        fila_textos = []
        for (cx, cy, cw, ch) in fila:
            recorte = roi[cy:cy+ch, cx:cx+cw]
            texto = _ocr_celda(recorte, lang=lang)
            if aplicar_postproc:
                texto = corregir_texto(texto)
            fila_textos.append(texto)
        datos.append(fila_textos)

    return _tabla_a_markdown(datos) if datos else None


def extraer_tablas_escaneado(
    imagenes: list[Image.Image],
    lang: str = "grc+eng",
    aplicar_postproc: bool = True,
    primera_pagina: int = 1,
) -> dict[int, list[str]]:
    """
    Extrae tablas de una lista de imágenes PIL (páginas ya convertidas).

    Parámetros
    ----------
    imagenes        : páginas como PIL.Image (de convert_from_path/bytes).
    lang            : idiomas Tesseract en formato 'grc+eng'.
    aplicar_postproc: pasa cada celda por corregir_texto().
    primera_pagina  : número de página real de imagenes[0] (para el informe).

    Devuelve
    --------
    {num_pagina_1based: [tabla_markdown, ...]}
    """
    resultado: dict[int, list[str]] = {}
    texto_anterior: Optional[str] = None

    for i, img in enumerate(imagenes):
        num_pagina = primera_pagina + i

        # OCR rápido de esta página (se reutiliza como texto_anterior para la siguiente)
        texto_pagina = pytesseract.image_to_string(img, lang=lang, config="--psm 3")

        tiene_caption = CAPTION_RE.search(texto_pagina) or (
            texto_anterior and CAPTION_RE.search(texto_anterior)
        )

        if tiene_caption:
            tabla_md = extraer_tabla_de_imagen(
                img,
                lang=lang,
                aplicar_postproc=aplicar_postproc,
                texto_pagina_anterior=texto_anterior,
                _texto_pagina=texto_pagina,   # evita repetir el OCR dentro
            )
            if tabla_md:
                resultado[num_pagina] = [tabla_md]
                print(f"[table_extractor] Pág. {num_pagina}: tabla extraída "
                      f"({tabla_md.count(chr(10))+1} filas)")
            else:
                print(f"[table_extractor] Pág. {num_pagina}: caption sin tabla visual")
        else:
            print(f"[table_extractor] Pág. {num_pagina}: sin caption, omitida")

        texto_anterior = texto_pagina

    return resultado


# ===========================================================================
# ROUTER PRINCIPAL
# ===========================================================================

def extraer_tablas(
    pdf_path: str,
    tipo: str,
    imagenes: Optional[list[Image.Image]] = None,
    lang: str = "grc+eng",
    aplicar_postproc: bool = True,
) -> dict[int, list[str]]:
    """
    Punto de entrada único.

    Parámetros
    ----------
    pdf_path     : ruta al PDF original (siempre necesaria).
    tipo         : "digital" (texto seleccionable) o "escaneado" (imágenes).
    imagenes     : páginas como PIL.Image; obligatorio si tipo="escaneado".
    lang         : idiomas Tesseract (solo flujo escaneado).
    aplicar_postproc: aplica corregir_texto() a cada celda.

    Devuelve
    --------
    {num_pagina: [tabla_markdown, ...]}
    """
    if tipo not in ("digital", "escaneado"):
        raise ValueError(f"tipo debe ser 'digital' o 'escaneado', no {tipo!r}")

    if tipo == "digital":
        return extraer_tablas_digital(pdf_path,
                                      aplicar_postproc=aplicar_postproc)
    else:
        if imagenes is None:
            raise ValueError(
                "Para PDFs escaneados pasa 'imagenes' "
                "(lista de PIL obtenida con convert_from_path)."
            )
        return extraer_tablas_escaneado(imagenes, lang=lang,
                                        aplicar_postproc=aplicar_postproc)


# ===========================================================================
# Formateo de resultado para incrustar en Markdown
# ===========================================================================

def tablas_a_texto(resultado: dict[int, list[str]]) -> str:
    """
    Convierte el dict {num_pagina: [md, ...]} en un bloque de texto Markdown
    listo para insertar en el documento de salida.
    """
    partes = []
    for num_pag, tablas in sorted(resultado.items()):
        for j, tabla in enumerate(tablas, 1):
            titulo = f"### Tabla {j} — Página {num_pag}"
            partes.append(f"{titulo}\n\n{tabla}")
    return "\n\n---\n\n".join(partes)
