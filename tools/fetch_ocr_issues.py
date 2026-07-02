#!/usr/bin/env python3
"""
Descarga los issues abiertos con la etiqueta 'ocr-correction' del repo
y genera las tuplas de ocr_postprocess.py listas para revisar y pegar.

No necesita nada más que Python (usa la API pública de GitHub, sin
autenticación, así que basta con que el repo sea público).

Uso:
    python tools/fetch_ocr_issues.py
    python tools/fetch_ocr_issues.py --selftest   # comprueba el parser
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request

REPO = "candellozanocarlos/PDF-TO-MARKDOWN-CLASSIC-GREEK"
API_URL = f"https://api.github.com/repos/{REPO}/issues?labels=ocr-correction&state=open"


def parse_body(body: str) -> dict[str, str]:
    """Convierte el cuerpo markdown de un issue-form ('### Etiqueta\\n\\nvalor')
    en un diccionario {etiqueta en minúsculas: valor}."""
    fields = {}
    for block in re.split(r"\n### ", body.strip()):
        block = block.lstrip("# ").strip()
        if "\n" not in block:
            continue
        label, _, value = block.partition("\n")
        fields[label.strip().lower()] = value.strip()
    return fields


def build_tuple(mal: str, bien: str, desc: str) -> str:
    desc = desc.replace("\n", " ").strip()
    return (
        f"    (re.compile({re.escape(mal)!r}, re.IGNORECASE | re.UNICODE),\n"
        f"     {bien!r},\n"
        f"     {desc!r}),"
    )


def main() -> None:
    with urllib.request.urlopen(API_URL) as resp:
        issues = json.load(resp)

    if not issues:
        print("No hay issues abiertos con la etiqueta 'ocr-correction'.")
        return

    general, corpus, incompletos = [], [], []
    for issue in issues:
        num = issue["number"]
        fields = parse_body(issue.get("body") or "")
        mal = fields.get("texto que salió mal", "")
        bien = fields.get("texto correcto", "")
        contexto = fields.get("frase completa (contexto)", "")
        alcance = fields.get(
            "¿este error se repite en cualquier documento o es propio de este pdf concreto?", ""
        )

        if not mal or not bien:
            incompletos.append((num, issue["html_url"]))
            continue

        desc = f"issue #{num}"
        if contexto and contexto != "_No response_":
            desc += f": {contexto[:60]}"
        tuple_str = build_tuple(mal, bien, desc)

        if alcance.startswith("Cualquier documento"):
            general.append((num, tuple_str))
        else:
            corpus.append((num, tuple_str))

    if general:
        print("# --- Pegar en REGEX_RULES_GENERAL o REGEX_RULES_GREEK ---")
        for _, t in general:
            print(t)
        print()

    if corpus:
        print("# --- Pegar en REGEX_RULES_CORPUS_SPECIFIC ---")
        for _, t in corpus:
            print(t)
        print()

    for num, url in incompletos:
        print(f"# issue #{num}: campos incompletos, revisar a mano -> {url}")

    nums = [str(n) for n, _ in general + corpus]
    if nums:
        print(
            f"\n# Cuando hayas pegado, probado (pytest tests/) y hecho commit,"
            f" cierra los issues:\n"
            f"#   gh issue close {' '.join(nums)} --comment \"Corregido, ver commit ...\"\n"
            f"# o manualmente desde https://github.com/{REPO}/issues"
        )


def _selftest() -> None:
    sample = (
        "### Texto que salió mal\n\nἐξetvat\n\n"
        "### Texto correcto\n\nἐξεῖναι\n\n"
        "### Frase completa (contexto)\n\n_No response_\n\n"
        "### ¿Este error se repite en cualquier documento o es propio de este PDF concreto?\n\n"
        "Cualquier documento (patrón general, p. ej. confusión de letras)\n\n"
        "### PDF de origen (opcional)\n\n_No response_"
    )
    fields = parse_body(sample)
    assert fields["texto que salió mal"] == "ἐξetvat"
    assert fields["texto correcto"] == "ἐξεῖναι"
    assert fields["frase completa (contexto)"] == "_No response_"
    assert build_tuple("a\\b", 'x"y', "d") == (
        "    (re.compile('a\\\\\\\\b', re.IGNORECASE | re.UNICODE),\n"
        "     'x\"y',\n"
        "     'd'),"
    )
    print("selftest OK")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
