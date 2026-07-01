"""
ocr_postprocess.py
------------------
Post-procesamiento de texto OCR para textos académicos multilingües
con griego antiguo (Tesseract grc+fra+deu+eng+spa).

Uso:
    from ocr_postprocess import corregir_texto

    texto_limpio = corregir_texto(texto_bruto)
    texto_limpio = corregir_texto(texto_bruto, verbose=True)

Las reglas están organizadas en secciones y son fácilmente ampliables.
Para añadir un patrón nuevo, basta con añadir una entrada al diccionario
correspondiente o una tupla a la lista de reglas correspondiente.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Constantes griegas
# ---------------------------------------------------------------------------

GREEK_CHAR = r"[Ͱ-Ͽἀ-῿]"

# Captura bloques griegos incluyendo corchetes Leiden intercalados (ἀγαθ[ο]ῦ).
# Permite un carácter de corchete entre dos secuencias griegas para no romper
# palabras epigráficas con lagunas en medio.
GREEK_RUN_RE = re.compile(
    r"[Ͱ-Ͽἀ-῿]+"
    r"(?:[\[\](){}⟨⟩][Ͱ-Ͽἀ-῿]+)*"
)

# Puntuación reconocida tras sigma final
_SIGMA_FINAL_LOOKAHEAD = r"""[\s,\.·;:\!\?\)\]\}»'"··]|$"""

# Partículas / monosílabos frecuentes: no unir con la palabra siguiente
GREEK_STOPWORDS = frozenset({
    "καὶ", "καί", "οὐ", "οὐκ", "οὐχ", "μὴ", "μή", "δὲ", "δέ", "γὰρ", "γάρ",
    "ἐν", "εἰ", "ὡς", "μὲν", "μέν", "ἡ", "ὁ", "οἱ", "αἱ", "τὰ", "τὸ", "τῇ",
    "τῷ", "ἐκ", "πρὸς", "πρὸ", "ἀπὸ", "μετὰ", "κατὰ", "παρὰ", "ὑπὸ", "ὑπὲρ",
    "ἀλλὰ", "ἄρα", "οὖν", "ἔτι", "οὐδὲ", "εἰς", "ἄν", "τε", "γε", "τι", "τις",
    "ἂν", "ἃν", "ὅτι", "ὅτε", "ὅπερ", "ὅπως", "ὅστις", "ὅσον", "ὅσοι",
})

# Mayúsculas latinas homógrafas → griegas en notación epigráfica <...>
# Ampliado: G→Γ, L→Λ, S→Σ, V→Υ respecto a la versión anterior
EPIGRAPHIC_LATIN_TO_GREEK = {
    "A": "Α", "B": "Β", "D": "Δ", "E": "Ε", "F": "Φ",
    "G": "Γ", "H": "Η", "I": "Ι", "K": "Κ", "L": "Λ",
    "M": "Μ", "N": "Ν", "O": "Ο", "P": "Ρ", "Q": "Ω",
    "S": "Σ", "T": "Τ", "V": "Υ", "X": "Χ", "Y": "Υ", "Z": "Ζ",
}

# Minúsculas latinas visualmente similares a griegas.
# Se aplican SOLO cuando la letra está rodeada de caracteres griegos.
LATIN_TO_GREEK_IN_RUN = {
    "a": "α", "b": "β", "e": "ε", "i": "ι", "k": "κ",
    "n": "ν", "o": "ο", "p": "ρ", "r": "ρ", "t": "τ",
    "u": "υ", "v": "ν", "w": "ω", "x": "χ",
}

# Lookbehind/lookahead fijos (un carácter griego) → sustitución sin consumir contexto
_LATIN_IN_GREEK_CTX_RE = re.compile(
    r"(?<=[Ͱ-Ͽἀ-῿])([a-z])(?=[Ͱ-Ͽἀ-῿])"
)

# ---------------------------------------------------------------------------
# 1. SUSTITUCIONES DE CARÁCTER ÚNICO
#    Errores sistemáticos del OCR independientes del contexto.
# ---------------------------------------------------------------------------

CHAR_REPLACEMENTS = {
    # Comillas tipográficas mal reconocidas (Windows-1252 → Unicode)
    "\x93": "“",
    "\x94": "”",
    "\x91": "‘",
    "\x92": "’",
    "\x85": "...",
    "\x96": "–",   # en-dash
    "\x97": "—",   # em-dash

    # Caracteres de control residuales
    "\x0c": "\n",       # form feed
    "\r\n": "\n",
    "\r": "\n",

    # Espacios especiales → espacio normal
    " ": " ",      # non-breaking space
    "​": "",       # zero-width space
    "‌": "",       # zero-width non-joiner
    "﻿": "",       # BOM

    # Ligaduras latinas mal segmentadas (frecuentes en PDFs antiguos)
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬆ": "st",
}

# ---------------------------------------------------------------------------
# 2. REGLAS GENERALES (todo el texto)
# ---------------------------------------------------------------------------

REGEX_RULES_GENERAL = [


    # --- Artefactos de paginación y cabeceras ---

    (re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE),
     "",
     "Elimina líneas que son solo números de página"),

    # --- Guiones de fin de línea (división silábica del original) ---

    (re.compile(r"(\w)-\n(\w)", re.UNICODE),
     r"\1\2",
     "Reúne palabras divididas con guión de fin de línea"),

    (re.compile(r"(\w)- \n(\w)", re.UNICODE),
     r"\1\2",
     "Reúne palabras divididas con guión+espacio de fin de línea"),

    # --- Espacios espurios ---

    (re.compile(r" {2,}"),
     " ",
     "Colapsa espacios múltiples"),

    (re.compile(r" ([,\.\!\?\:\;])(?!\s*\n)"),
     r"\1",
     "Elimina espacio antes de puntuación"),

    (re.compile(r"\n{3,}"),
     "\n\n",
     "Colapsa líneas en blanco múltiples"),

    # --- Confusiones numéricas en contexto latino ---

    (re.compile(
        r"(?<=[a-záéíóúàèìòùäëïöüâêîôûæœ])1(?=[a-záéíóúàèìòùäëïöüâêîôûæœ])",
        re.IGNORECASE | re.UNICODE,
    ),
     "l",
     "1 entre letras latinas → l"),

    (re.compile(
        r"(?<=[a-záéíóúàèìòùäëïöüâêîôûæœ])0(?=[a-záéíóúàèìòùäëïöüâêîôûæœ])",
        re.IGNORECASE | re.UNICODE,
    ),
     "o",
     "0 entre letras latinas → o"),

    # --- Confusiones multi-carácter de Tesseract en contexto griego ---
    # Se aplican aquí (antes de la segmentación) porque los chars implicados
    # son latinos y romperían el run griego si no se tratan primero.

    (re.compile(rf"(?<={GREEK_CHAR})ij|ij(?={GREEK_CHAR})"),
     "η",
     "ij en contexto griego → η"),

    (re.compile(rf"(?<={GREEK_CHAR})rj|rj(?={GREEK_CHAR})"),
     "η",
     "rj en contexto griego → η"),

    (re.compile(rf"(?<={GREEK_CHAR})cp|cp(?={GREEK_CHAR})"),
     "φ",
     "cp en contexto griego → φ"),

    (re.compile(rf"(?<={GREEK_CHAR})<p|<p(?={GREEK_CHAR})"),
     "φ",
     "<p en contexto griego → φ"),

    (re.compile(rf"(?<={GREEK_CHAR})©|©(?={GREEK_CHAR})"),
     "θ",
     "© en contexto griego → θ (theta)"),

    # --- Referencias bibliográficas ---

    (re.compile(r"\bp p\.\s*(\d)"),
     r"pp. \1",
     "Corrige 'p p.' → 'pp.'"),

    (re.compile(r"\bI bid\b", re.IGNORECASE),
     "Ibid",
     "Corrige 'I bid' → 'Ibid'"),

    (re.compile(r"\bop\s*\.\s*cit\s*\."),
     "op. cit.",
     "Normaliza 'op. cit.'"),

    # --- Artefactos de columnas y tablas ---

    (re.compile(r"\t+"),
     " ",
     "Convierte tabulaciones en espacios"),

    (re.compile(r"^\s*[-=\*]{3,}\s*$", re.MULTILINE),
     "",
     "Elimina líneas separadoras de columna"),

    # --- Ortografía académica francesa ---

    (re.compile(r"«\s+"),
     "« ",
     "Normaliza espacio tras «"),

    (re.compile(r"\s+»"),
     " »",
     "Normaliza espacio antes de »"),

    # --- Notación fonética (IPA) ---

    (re.compile(r"/9:/"),
     "/ɔː/",
     "/9:/ → /ɔː/ (IPA)"),

    (re.compile(r"\[9:\]"),
     "[ɔː]",
     "[9:] → [ɔː] (IPA)"),

    (re.compile(r'/"([a-zA-Zɑ-ɿʀ-ʿ])'),
     r"/ʰ\1",
     '/" → /ʰ (aspirada IPA)'),
]

# ---------------------------------------------------------------------------
# 2b. REGLAS ESPECÍFICAS DE CORPUS
# Generadas automáticamente por ocr_ml_detector.py (herramienta interna, no
# incluida en este repositorio) a partir de errores observados en documentos
# concretos ya procesados. Se mantienen separadas de REGEX_RULES_GENERAL
# porque son correcciones ad hoc (nombres propios, fragmentos de palabras
# muy específicos) que no tiene sentido aplicar a un PDF nuevo. Actívalas con
# corregir_texto(texto, incluir_corpus_especifico=True) si vas a reprocesar
# el mismo corpus de siempre.
# ---------------------------------------------------------------------------

REGEX_RULES_CORPUS_ESPECIFICO = [
    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Ilioaı", re.IGNORECASE | re.UNICODE),
     "llioaı",
     "Il→ll al inicio (Ileno→lleno, Ilama→llama)"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Ηellenistic", re.IGNORECASE | re.UNICODE),
     "Ηellenιstιc",
     "Script mixto griego+latino: 'i'→'ι'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"AAλοιρ", re.IGNORECASE | re.UNICODE),
     "ΑΑλοιρ",
     "Script mixto griego+latino: 'A'→'Α'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"önnoσίων", re.IGNORECASE | re.UNICODE),
     "önnοσίων",
     "Script mixto griego+latino: 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"ἐξetvat", re.IGNORECASE | re.UNICODE),
     "ἐξetνat",
     "Script mixto griego+latino: 'v'→'ν'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"xeoάσθο", re.IGNORECASE | re.UNICODE),
     "xeοάσθο",
     "Script mixto griego+latino: 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"duyaδεύαντι", re.IGNORECASE | re.UNICODE),
     "dυyaδεύαντι",
     "Script mixto griego+latino: 'u'→'υ'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"ΙN", re.IGNORECASE | re.UNICODE),
     "ΙΝ",
     "Script mixto griego+latino: 'N'→'Ν'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Develἢ", re.IGNORECASE | re.UNICODE),
     "Deνelἢ",
     "Script mixto griego+latino: 'v'→'ν'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"SUMMARΥ", re.IGNORECASE | re.UNICODE),
     "SUΜΜΑRΥ",
     "Script mixto griego+latino: 'M'→'Μ' 'A'→'Α'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Agteptρίαν", re.IGNORECASE | re.UNICODE),
     "Αgteρtρίαν",
     "Script mixto griego+latino: 'A'→'Α' 'p'→'ρ'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"φαAvgöv", re.IGNORECASE | re.UNICODE),
     "φαΑνgöν",
     "Script mixto griego+latino: 'A'→'Α' 'v'→'ν'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"XQEOTEQκαὶ", re.IGNORECASE | re.UNICODE),
     "ΧQΕΟΤΕQκαὶ",
     "Script mixto griego+latino: 'X'→'Χ' 'E'→'Ε' 'O'→'Ο' 'T'→'Τ'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Zußagiται", re.IGNORECASE | re.UNICODE),
     "Ζυßagιται",
     "Script mixto griego+latino: 'Z'→'Ζ' 'u'→'υ' 'i'→'ι'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Εéveoc", re.IGNORECASE | re.UNICODE),
     "Εéνeοc",
     "Script mixto griego+latino: 'v'→'ν' 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"SENSΕ", re.IGNORECASE | re.UNICODE),
     "SΕΝSΕ",
     "Script mixto griego+latino: 'E'→'Ε' 'N'→'Ν'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"BRΟAD", re.IGNORECASE | re.UNICODE),
     "ΒRΟΑD",
     "Script mixto griego+latino: 'B'→'Β' 'A'→'Α'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"TΗE", re.IGNORECASE | re.UNICODE),
     "ΤΗΕ",
     "Script mixto griego+latino: 'T'→'Τ' 'E'→'Ε'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Ηesychios", re.IGNORECASE | re.UNICODE),
     "Ηesychιοs",
     "Script mixto griego+latino: 'i'→'ι' 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"BeiAoμαι", re.IGNORECASE | re.UNICODE),
     "ΒeιΑομαι",
     "Script mixto griego+latino: 'B'→'Β' 'i'→'ι' 'A'→'Α' 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"PöAoμαι", re.IGNORECASE | re.UNICODE),
     "ΡöΑομαι",
     "Script mixto griego+latino: 'P'→'Ρ' 'A'→'Α' 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"CΥPRΙΟT", re.IGNORECASE | re.UNICODE),
     "CΥΡRΙΟΤ",
     "Script mixto griego+latino: 'P'→'Ρ' 'T'→'Τ'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"NOΝΟΥΣ", re.IGNORECASE | re.UNICODE),
     "ΝΟΝΟΥΣ",
     "Script mixto griego+latino: 'N'→'Ν' 'O'→'Ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"CΥPRIΟT", re.IGNORECASE | re.UNICODE),
     "CΥΡRΙΟΤ",
     "Script mixto griego+latino: 'P'→'Ρ' 'I'→'Ι' 'T'→'Τ'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"MYCENAΕAN", re.IGNORECASE | re.UNICODE),
     "ΜYCΕΝΑΕΑΝ",
     "Script mixto griego+latino: 'M'→'Μ' 'E'→'Ε' 'N'→'Ν' 'A'→'Α'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Ηomeric", re.IGNORECASE | re.UNICODE),
     "Ηοmerιc",
     "Script mixto griego+latino: 'o'→'ο' 'i'→'ι'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Ιonic", re.IGNORECASE | re.UNICODE),
     "Ιοnιc",
     "Script mixto griego+latino: 'o'→'ο' 'i'→'ι'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"Εuboean", re.IGNORECASE | re.UNICODE),
     "Ευbοean",
     "Script mixto griego+latino: 'u'→'υ' 'o'→'ο'"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"ovvavφότεροι", re.IGNORECASE | re.UNICODE),
     "ovvaνφότεροι",
     "v latino→ν (nu) adyacente a griego"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"κἐλευλύvıa", re.IGNORECASE | re.UNICODE),
     "κἐλευλύνıa",
     "v latino→ν (nu) adyacente a griego"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"ivbooßievεἰ", re.IGNORECASE | re.UNICODE),
     "ivbooßieνεἰ",
     "v latino→ν (nu) adyacente a griego"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"acentuaci6n", re.IGNORECASE | re.UNICODE),
     "acentuación",
     "ci6n→ción (terminación nominal)"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"absorci6n", re.IGNORECASE | re.UNICODE),
     "absorción",
     "ci6n→ción (terminación nominal)"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"pronunciaci6n", re.IGNORECASE | re.UNICODE),
     "pronunciación",
     "ci6n→ción (terminación nominal)"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"‘espafiol’", re.IGNORECASE | re.UNICODE),
     "‘español’",
     "espafiol→español"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"formulaci6n", re.IGNORECASE | re.UNICODE),
     "formulación",
     "ci6n→ción (terminación nominal)"),


    # Detectado automáticamente por ocr_ml_detector.py
    (re.compile(r"relaci6n", re.IGNORECASE | re.UNICODE),
     "relación",
     "ci6n→ción (terminación nominal)"),
]

# ---------------------------------------------------------------------------
# 3. REGLAS GRIEGAS (solo bloques con caracteres griegos)
# ---------------------------------------------------------------------------

REGEX_RULES_GRIEGO = [

    # Sigma final: σ → ς ante espacio, puntuación o fin de línea
    (re.compile(
        rf"σ(?={_SIGMA_FINAL_LOOKAHEAD})",
        re.MULTILINE | re.UNICODE,
    ),
     "ς",
     "σ ante espacio/puntuación → ς (sigma final)"),

    # Confusiones de Tesseract grc documentadas
    (re.compile(r"\(ρ"),  "φ",  "(ρ → φ"),
    (re.compile(r"cp"),   "φ",  "cp → φ dentro de bloque griego"),
    (re.compile(r"<p"),   "φ",  "<p → φ dentro de bloque griego"),

    # Punto y coma ASCII dentro de palabra griega (confusión con ano teleia ·)
    (re.compile(rf"(?<={GREEK_CHAR});(?={GREEK_CHAR})"),
     "",
     "; espúreo dentro de palabra griega"),

    # Apóstrofo / espíritu suelto intra-palabra (diacrítico separado por el OCR)
    (re.compile(rf"(?<={GREEK_CHAR})[̓̔’'](?={GREEK_CHAR})"),
     "",
     "Espíritu o apóstrofo suelto intra-palabra"),
]

# Alias para compatibilidad con código externo
REGEX_RULES = REGEX_RULES_GENERAL + REGEX_RULES_CORPUS_ESPECIFICO + REGEX_RULES_GRIEGO

# ---------------------------------------------------------------------------
# 4. SUSTITUCIONES DE PALABRAS COMPLETAS (contexto latino / académico)
# ---------------------------------------------------------------------------

WORD_REPLACEMENTS = {
    "lhéte": "Lhôte",
    "dopdonna": "dodona",
    "fiir": "für",
    "lingiiista": "lingüista",
    "geminaciOn": "geminación",
    "sefiala": "señala",
    "preposiciOn": "preposición",
    "sefialé": "señalé",
    "oraciOn": "oración",
    "negaciOn": "negación",
    "variaciOn": "variación",
    "entonaciOn": "entonación",
    "formulaciOn": "formulación",
    "pequenios": "pequeños",
    "afios": "años",
    "lingiistas": "lingüistas",
    "acentuaciOn": "acentuación",
    "lingiiisticos": "lingüisticos",
    "Filologia": "Filología",
    "Lingiiistica": "lingüística",
    "Zeitschrifi": "Zeitschrift",
    "Zeitschnft":  "Zeitschrift",
    "G1otta":      "Glotta",
    "Hespena":     "Hesperia",
    "Mnemosvne":   "Mnemosyne",
    "ibid":        "ibid.",
    "Ibid":        "Ibid.",
    "epigratia":   "epigrafía",
    "epigrafia":   "epigrafía",
    "fonologia":   "fonología",
    "morfologa":   "morfología",
    "inscnpcion":  "inscripción",
    "inscripcion": "inscripción",
}

# Patrones compilados una vez al cargar el módulo (evita recompilar en cada llamada)
_WORD_PATTERNS = [
    (re.compile(r"\b" + re.escape(error) + r"\b", re.UNICODE), correcto)
    for error, correcto in WORD_REPLACEMENTS.items()
]

# ---------------------------------------------------------------------------
# 5. FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def _aplicar_char_replacements(texto: str) -> str:
    for original, reemplazo in CHAR_REPLACEMENTS.items():
        texto = texto.replace(original, reemplazo)
    return texto


def _aplicar_regex_rules(texto: str, reglas: list) -> str:
    for patron, reemplazo, _descripcion in reglas:
        texto = patron.sub(reemplazo, texto)
    return texto


def _aplicar_word_replacements(texto: str) -> str:
    for patron, correcto in _WORD_PATTERNS:
        texto = patron.sub(correcto, texto)
    return texto


def _normalizar_unicode(texto: str) -> str:
    """Normaliza a NFC (forma canónica compuesta), estándar para griego politónico."""
    return unicodedata.normalize("NFC", texto)


def _limpiar_notacion_leiden(texto: str) -> str:
    """
    Elimina espacios espurios que el OCR introduce dentro de los corchetes
    de notación epigráfica Leiden: [ ] ( ) { } ⟨ ⟩
    Ejemplo: '[ ἀγαθ οῦ ]' → '[ἀγαθοῦ]'
    """
    for apertura, cierre in [("\\[", "\\]"), ("\\(", "\\)"), ("\\{", "\\}"), ("⟨", "⟩")]:
        texto = re.sub(apertura + r"\s+", apertura.replace("\\", ""), texto)
        texto = re.sub(r"\s+" + cierre, cierre.replace("\\", ""), texto)
    return texto


def _sustituir_latinas_en_contexto_griego(texto: str) -> str:
    """
    Sustituye letras latinas minúsculas situadas entre dos caracteres griegos
    por su equivalente griego visual (α, ε, ν, ο, ρ…).
    Solo actúa cuando la letra latina está flanqueada por Unicode griego,
    lo que garantiza que el contexto es un bloque griego y no texto latino.
    """
    return _LATIN_IN_GREEK_CTX_RE.sub(
        lambda m: LATIN_TO_GREEK_IN_RUN.get(m.group(1), m.group(1)),
        texto,
    )


def _corregir_notacion_epigrafica(texto: str) -> str:
    """Convierte mayúsculas latinas homógrafas dentro de <...> a griegas."""
    def _reemplazar(match: re.Match) -> str:
        contenido = match.group(1)
        for latina, griega in EPIGRAPHIC_LATIN_TO_GREEK.items():
            contenido = contenido.replace(latina, griega)
        return f"<{contenido}>"
    return re.sub(r"<([^>]+)>", _reemplazar, texto)


def _unir_espacios_intra_palabra_griega(texto: str, max_iteraciones: int = 5) -> str:
    """
    Reúne espacios OCR espurios entre fragmentos griegos contiguos.
    No une si ambos fragmentos tienen ≥ 4 caracteres (probablemente
    son palabras completas, no fragmentos de una misma palabra).
    """
    patron = re.compile(rf"([Ͱ-Ͽἀ-῿]+) ([Ͱ-Ͽἀ-῿]+)")

    def _maybe_join(match: re.Match) -> str:
        izquierda, derecha = match.group(1), match.group(2)
        if izquierda in GREEK_STOPWORDS or derecha in GREEK_STOPWORDS:
            return match.group(0)
        # Ambos fragmentos largos → probablemente palabras distintas
        if len(izquierda) >= 4 and len(derecha) >= 4:
            return match.group(0)
        return izquierda + derecha

    for _ in range(max_iteraciones):
        nuevo = patron.sub(_maybe_join, texto)
        if nuevo == texto:
            break
        texto = nuevo
    return texto


def _procesar_bloque_griego(texto: str) -> str:
    """Aplica correcciones específicas de griego a un bloque ya segmentado."""
    texto = _aplicar_regex_rules(texto, REGEX_RULES_GRIEGO)
    texto = _unir_espacios_intra_palabra_griega(texto)
    return texto


def _segmentar_y_procesar(texto: str, aplicar_griego: bool = True) -> str:
    """
    Recorre el texto en una sola pasada aplicando:
    - A bloques griegos: reglas griegas (si aplicar_griego=True).
    - A bloques no griegos: sustituciones léxicas latinas.
    Fusiona las dos pasadas anteriores (_segmentar_y_procesar_griego y
    _procesar_bloques_no_griegos) en un único bucle.
    """
    partes = []
    ultimo_fin = 0
    for match in GREEK_RUN_RE.finditer(texto):
        if match.start() > ultimo_fin:
            partes.append(_aplicar_word_replacements(texto[ultimo_fin:match.start()]))
        bloque = match.group(0)
        partes.append(_procesar_bloque_griego(bloque) if aplicar_griego else bloque)
        ultimo_fin = match.end()
    if ultimo_fin < len(texto):
        partes.append(_aplicar_word_replacements(texto[ultimo_fin:]))
    return "".join(partes)


# ---------------------------------------------------------------------------
# 6. FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def corregir_texto(
    texto: str,
    verbose: bool = False,
    modo: str = "completo",
    incluir_corpus_especifico: bool = False,
) -> str:
    """
    Aplica el pipeline completo de post-procesamiento al texto OCR.

    Parámetros
    ----------
    texto   : str  — Texto crudo devuelto por pytesseract.
    verbose : bool — Si True, imprime estadísticas de caracteres.
    modo    : str
        - "completo" (defecto): reglas generales + griego + epigrafía.
        - "general": solo reglas generales y epigrafía (sin correcciones griegas).
        - "griego": alias explícito de "completo".
    incluir_corpus_especifico : bool
        Si True, aplica también REGEX_RULES_CORPUS_ESPECIFICO (correcciones ad
        hoc aprendidas de documentos concretos ya procesados). Déjalo en False
        para un PDF nuevo que no forme parte de ese corpus.

    Devuelve
    --------
    str — Texto corregido.
    """
    if modo not in ("completo", "general", "griego"):
        raise ValueError(f"modo no válido: {modo!r}. Use 'completo', 'general' o 'griego'.")

    if verbose:
        print(f"    [postproc] Caracteres antes: {len(texto)}")

    texto = _normalizar_unicode(texto)
    texto = _aplicar_char_replacements(texto)
    texto = _limpiar_notacion_leiden(texto)                   # antes de segmentar
    texto = _sustituir_latinas_en_contexto_griego(texto)      # antes de segmentar
    texto = _aplicar_regex_rules(texto, REGEX_RULES_GENERAL)
    if incluir_corpus_especifico:
        texto = _aplicar_regex_rules(texto, REGEX_RULES_CORPUS_ESPECIFICO)
    texto = _corregir_notacion_epigrafica(texto)
    texto = _segmentar_y_procesar(texto, aplicar_griego=(modo in ("completo", "griego")))
    texto = texto.strip()

    if verbose:
        print(f"    [postproc] Caracteres después: {len(texto)}")

    return texto
