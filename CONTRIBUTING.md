# Cómo incorporar correcciones de OCR reportadas por otras personas

Este documento explica el flujo de trabajo para que usuarios del programa
(con o sin conocimientos técnicos) reporten errores de OCR que ven en el
`.md` generado, y cómo el mantenedor los convierte en reglas dentro de
`ocr_postprocess.py`.

## 1. La persona usuaria reporta el error

Comparte con ella la aplicación de doble clic (sección "For non-technical
users" del README), no el repositorio. Cuando vea un error en el `.md`
resultante, que abra un Issue nuevo aquí:

**https://github.com/candellozanocarlos/PDF-TO-MARKDOWN-CLASSIC-GREEK/issues/new/choose**

Debe elegir la plantilla **"Corrección de OCR"**
(`.github/ISSUE_TEMPLATE/correccion_ocr.yml`), que le pide 4 campos:

| Campo | Para qué sirve |
| --- | --- |
| Texto que salió mal | El texto tal cual aparece en el `.md` |
| Texto correcto | Cómo debería haber salido |
| Frase completa (contexto) | Evita confundir el error con una palabra parecida |
| ¿Cualquier documento o solo este PDF? | Decide en qué lista de reglas entra la corrección (ver más abajo) |

El campo de alcance es clave: le ahorra al mantenedor tener que volver a
preguntar si el error es un patrón general (p. ej. una letra latina que se
confunde sistemáticamente con una griega) o algo específico de ese
documento (un nombre propio, un fragmento muy concreto).

## 2. El mantenedor descarga los issues pendientes

```powershell
cd "C:\Users\Carlos Candel\OneDrive - UVa\PYTHON\PDF-TO-MARKDOWN-CLASSIC-GREEK"
python tools/fetch_ocr_issues.py
```

`tools/fetch_ocr_issues.py` llama a la API pública de GitHub (no necesita
`gh` CLI ni autenticación, basta con que el repo sea público), descarga
todos los issues abiertos con la etiqueta `ocr-correction`, y para cada
uno imprime una tupla ya lista en el formato que usa `ocr_postprocess.py`:

```python
(re.compile('ἐξetvat', re.IGNORECASE | re.UNICODE),
 'ἐξεῖναι',
 'issue #12: frase de contexto...'),
```

Las agrupa en dos bloques según el campo de alcance:

- **"Pegar en REGEX_RULES_GENERAL o REGEX_RULES_GREEK"** → patrones que se
  repiten en cualquier documento.
- **"Pegar en REGEX_RULES_CORPUS_SPECIFIC"** → correcciones ad hoc de un
  PDF concreto (solo se aplican si se llama a
  `fix_text(text, include_corpus_specific=True)`).

Los issues con campos incompletos se listan aparte para revisarlos a
mano, y al final el script sugiere el comando para cerrar todos los
issues procesados de una vez (`gh issue close ...`, si tienes `gh` CLI
instalado) o recuerda que se pueden cerrar manualmente desde la web.

Comprobación rápida de que el parser sigue funcionando después de tocar
el script:

```powershell
python tools/fetch_ocr_issues.py --selftest
```

## 3. Revisar y pegar las reglas

Cada tupla generada usa por defecto un patrón **literal** (`re.escape`
del texto reportado). Antes de pegarla en `ocr_postprocess.py`:

- Revisa si el error es realmente un caso aislado o si conviene
  **generalizar el regex** (p. ej. cambiar una letra concreta por una
  clase de caracteres, si el mismo tipo de confusión aparece en más
  palabras).
- Pega cada tupla en la lista que le corresponda:
  `REGEX_RULES_GENERAL`, `REGEX_RULES_GREEK` o
  `REGEX_RULES_CORPUS_SPECIFIC` (ver la cabecera de cada sección en
  `ocr_postprocess.py` para más detalle).

## 4. Verificar

```powershell
pip install -r requirements-dev.txt   # solo la primera vez
pytest tests/ -v
```

Si alguna regla nueva choca con una regla existente, algún test debería
fallar antes de llegar a producción.

## 5. Publicar y cerrar los issues

```powershell
git add ocr_postprocess.py
git commit -m "Añade correcciones de OCR reportadas en issues"
git push
```

Cierra los issues correspondientes (comando sugerido por el propio
script, o manualmente desde la pestaña Issues de GitHub).
