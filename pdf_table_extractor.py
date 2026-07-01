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

# Coincide con una celda que es solo un número (con o sin decimales). Estas
# celdas NO deben pasar por el pipeline general de corregir_texto(), porque
# incluye una regla pensada para eliminar números de página sueltos
# (patrón "^\s*\d{1,4}\s*$") que, aplicada al contenido de una celda,
# borraría cualquier dato puramente numérico de la tabla (edades, años,
# cantidades...). Ese contexto (texto corrido de página vs. celda aislada)
# es justamente la diferencia que la regla no puede distinguir por sí sola.
_CELDA_SOLO_NUMERO = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*$")


def _corregir_celda(texto: Optional[str]) -> str:
    """Aplica corregir_texto() a una celda, salvo que sea un número aislado."""
    if not texto:
        return ""
    if _CELDA_SOLO_NUMERO.match(texto):
        return texto.strip()
    return corregir_texto(texto)

# ---------------------------------------------------------------------------
# Patrón de pie de TABLA (multilingüe). Solo se busca una tabla si la página
# contiene uno de estos pies. Los pies de figura ("Figure", "Fig.", "Abb.",
# "Tav.") se excluyen deliberadamente: una figura no es una tabla, e incluirlos
# generaba falsos positivos (el extractor intentaba leer una tabla en páginas
# que en realidad tenían un mapa o una fotografía).
# ---------------------------------------------------------------------------
CAPTION_RE = re.compile(
    r"^\s*(?:Table|Tab\.?|Tabla|Cuadro|Tableau)\s*\.?\s*\d+",
    re.IGNORECASE | re.MULTILINE,
)

# Patrón de pie de figura, mantenido aparte por si se quiere usar en el futuro
# para un extractor de figuras independiente. No se usa en este módulo.
CAPTION_RE_FIGURA = re.compile(
    r"^\s*(?:Figure|Fig\.?|Abbildung|Abb\.?|Tav\.?)\s*\.?\s*\d+",
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
        """
        Descarta estructuras que no son tablas de verdad. Criterios (todos
        deben cumplirse):
          - Al menos 3 filas y al menos 2 columnas en la fila más frecuente.
          - >= 75 % de las filas tienen ese mismo número de columnas
            (antes 60 %; un 60 % dejaba pasar recuadros irregulares).
          - >= 50 % de las celdas tienen contenido no vacío (descarta grids
            de líneas detectadas sobre una zona mayoritariamente en blanco,
            p. ej. el margen de una página o una caja decorativa).
        """
        if not tabla or len(tabla) < 3:
            return False
        n_cols = [len(fila) for fila in tabla]
        if max(n_cols) < 2:
            return False
        modo = max(set(n_cols), key=n_cols.count)
        if modo < 2:
            return False
        consistencia = sum(1 for n in n_cols if n == modo) / len(tabla)
        if consistencia < 0.75:
            return False
        total_celdas = sum(len(fila) for fila in tabla)
        celdas_no_vacias = sum(
            1 for fila in tabla for c in fila if c and str(c).strip()
        )
        return total_celdas > 0 and (celdas_no_vacias / total_celdas) >= 0.5

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
                        [_corregir_celda(c) for c in fila]
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
    y verticales. Buscamos el contorno del área de líneas que contiene más
    intersecciones. Exigimos:
      - Al menos 9 intersecciones (equivalente a un grid mínimo de 3x3
        celdas; antes se aceptaban 4, es decir un simple 2x2, demasiado
        permisivo y fácil de confundir con un recuadro o un logo con marco).
      - El área del bbox debe ser al menos un 2 % de la imagen completa,
        para descartar recuadros pequeños (sellos, cabeceras con marco,
        iconos) que no son tablas de datos.
    """
    h_total, w_total = img_gray.shape
    lineas_h, lineas_v = _separar_lineas(img_gray)

    # Píxeles en los que coinciden línea horizontal Y vertical → intersecciones
    intersecciones = cv2.bitwise_and(lineas_h, lineas_v)
    if cv2.countNonZero(intersecciones) < 9:
        return None

    # Un simple recuadro/marco (sin líneas internas) tiene igualmente 2
    # componentes horizontales (borde superior + inferior) y 2 verticales
    # (borde izquierdo + derecho), así que un umbral de ">= 2" no lo
    # distingue de una tabla real. El grid mínimo aceptado es 3 filas x 2
    # columnas, que requiere 4 líneas horizontales (bordes + 2 divisorias
    # internas) y 3 verticales (bordes + 1 divisoria interna); exigimos
    # exactamente eso como mínimo.
    n_h = cv2.connectedComponents(lineas_h)[0] - 1  # -1: descuenta el fondo
    n_v = cv2.connectedComponents(lineas_v)[0] - 1
    if n_h < 4 or n_v < 3:
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

    if mejor_bbox is None or mejor_n < 9:
        return None

    _, _, bw, bh = mejor_bbox
    area_rel = (bw * bh) / (w_total * h_total)
    if area_rel < 0.02:
        return None

    return mejor_bbox


# ── 2c. Detección y agrupación de celdas ────────────────────────────────────

def _posiciones_lineas(mascara_linea: np.ndarray, eje: str) -> list[int]:
    """
    Localiza la posición (coordenada central) de cada línea de tabla dentro
    de una máscara binaria de líneas horizontales o verticales.

    Exige que la línea cubra al menos el 60 % de la dimensión perpendicular
    para contarla como línea real de la rejilla (un trazo corto de ruido, o
    un subrayado suelto, no llega a ese umbral y se descarta).

    Parámetros
    ----------
    eje : 'h' para líneas horizontales (se devuelven posiciones Y),
          'v' para líneas verticales (se devuelven posiciones X).
    """
    if eje == "h":
        perfil = (mascara_linea > 0).sum(axis=1)  # nº de píxeles de línea por fila
        dim_perpendicular = mascara_linea.shape[1]
    else:
        perfil = (mascara_linea > 0).sum(axis=0)  # nº de píxeles de línea por columna
        dim_perpendicular = mascara_linea.shape[0]

    umbral = dim_perpendicular * 0.6
    activos = perfil >= umbral

    posiciones = []
    en_racha = False
    inicio = 0
    for i, val in enumerate(activos):
        if val and not en_racha:
            en_racha, inicio = True, i
        elif not val and en_racha:
            en_racha = False
            posiciones.append((inicio + i - 1) // 2)
    if en_racha:
        posiciones.append((inicio + len(activos) - 1) // 2)

    return posiciones


def _detectar_celdas(roi: np.ndarray) -> list[tuple[int, int, int, int]]:
    """
    Reconstruye la rejilla de la tabla a partir de las posiciones reales de
    las líneas horizontales y verticales, y devuelve cada celda como
    (x, y, w, h), ordenadas por fila y luego por columna.

    Este método (basado en el perfil de línea, no en contornos) es más
    robusto que localizar "huecos" entre líneas por contornos: no depende de
    que la rejilla esté perfectamente cerrada en los píxeles del borde del
    recorte, que es una fuente habitual de fallos con OpenCV cuando la
    tabla ocupa el recorte al límite.
    """
    h, w = roi.shape
    lineas_h, lineas_v = _separar_lineas(roi)

    ys = _posiciones_lineas(lineas_h, "h")
    xs = _posiciones_lineas(lineas_v, "v")

    margen = 3   # evita capturar los propios píxeles de la línea en el recorte de celda
    min_lado = 10  # celdas más estrechas que esto se consideran ruido, no datos

    celdas: list[tuple[int, int, int, int]] = []
    for i in range(len(ys) - 1):
        y1, y2 = ys[i], ys[i + 1]
        if (y2 - y1) < min_lado:
            continue
        for j in range(len(xs) - 1):
            x1, x2 = xs[j], xs[j + 1]
            if (x2 - x1) < min_lado:
                continue
            cx, cy = x1 + margen, y1 + margen
            cw, ch = max((x2 - x1) - 2 * margen, 1), max((y2 - y1) - 2 * margen, 1)
            celdas.append((cx, cy, cw, ch))

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
    Verifica que las filas formen un grid coherente. Todos deben cumplirse:
    - Al menos 3 filas y 2 columnas (antes 2 filas: un grid 2xN es demasiado
      fácil de producir con ruido de OCR o líneas mal detectadas).
    - >= 80 % de las filas tienen el mismo número de columnas (antes 70 %).
    """
    if len(filas) < 3:
        return False
    n_cols = [len(f) for f in filas]
    if max(n_cols) < 2:
        return False
    modo = max(set(n_cols), key=n_cols.count)
    if modo < 2:
        return False
    return sum(1 for n in n_cols if n == modo) >= max(2, len(filas) * 0.8)


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
    if len(celdas) < 6:  # antes 4; el grid mínimo válido ahora es 3 filas x 2 cols = 6
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
                texto = _corregir_celda(texto)
            fila_textos.append(texto)
        datos.append(fila_textos)

    if not datos:
        return None

    # Verificación final: si tras el OCR la mayoría de las celdas están vacías,
    # lo detectado probablemente no era una tabla de datos real (podía ser un
    # recuadro decorativo o una figura con marco), así que se descarta.
    total_celdas = sum(len(f) for f in datos)
    celdas_con_texto = sum(1 for f in datos for c in f if c.strip())
    if total_celdas == 0 or (celdas_con_texto / total_celdas) < 0.5:
        return None

    return _tabla_a_markdown(datos)


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
# Inserción de tablas en el texto (compartida por pdf_to_markdown.py y las GUI)
# ===========================================================================

def insertar_tablas_en_texto(texto: str, tablas_md: list[str]) -> str:
    """
    Inserta cada tabla en Markdown justo después de la LÍNEA completa que
    contiene su caption (no solo después del número), para no partir la
    frase del pie de tabla por la mitad (p. ej. "Table 1. Sample data" no
    debe quedar cortado entre "Table 1" y ". Sample data").
    """
    if not tablas_md:
        return texto
    matches = list(CAPTION_RE.finditer(texto))
    if not matches:
        return texto

    partes, prev_end = [], 0
    for i, m in enumerate(matches):
        fin_linea = texto.find("\n", m.end())
        fin_linea = len(texto) if fin_linea == -1 else fin_linea
        partes.append(texto[prev_end:fin_linea])
        if i < len(tablas_md):
            partes.append(f"\n\n{tablas_md[i]}\n")
        prev_end = fin_linea
    partes.append(texto[prev_end:])
    return "".join(partes)


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
