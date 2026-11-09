#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_corpus_rules.py
---------------------
Builds verification/corpus_rules_provenance.json: one entry per rule of
REGEX_RULES_CORPUS_SPECIFIC (active) and REGEX_RULES_CORPUS_DISABLED, with the commit that introduced it (via
`git blame`), a human-readable source label, and risk flags.

Why: the corpus-specific rules were learned from specific documents. To
report OCR accuracy honestly, a document must be evaluated with the rules
learned from it switched off (see fix_text(corpus_specific_exclude=...)).
This file is what makes that possible and makes the rule set auditable.

Usage (from the repository root):
    python tools/audit_corpus_rules.py            # rewrite the JSON
    python tools/audit_corpus_rules.py --summary  # also print a summary
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ocr_postprocess as ocr  # noqa: E402

SRC = ROOT / "ocr_postprocess.py"
OUT = ROOT / "verification" / "corpus_rules_provenance.json"

# Commit prefix -> source label. Commits not listed fall back to their summary.
SOURCE_LABELS = {
    "082ac67": "unrecorded (before the 1 Jul 2026 rename; origin not kept)",
    "5d11833": "Brill/Mnemosyne PDFs (4 Jul 2026)",
    "6e91b8e": "Alonso Deniz 2022, p. 2",
    "9d21362": "Alonso Deniz 2022, p. 2",
}

_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
_LATIN = re.compile(r"[A-Za-z]")


def _rule_lines(name: str) -> list[int]:
    """Line number of each tuple inside the list called `name`."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == name
                        for t in node.targets)):
            return [elt.lineno for elt in node.value.elts]
    raise SystemExit(f"{name} not found")


def _blame(line: int) -> tuple[str, str]:
    out = subprocess.run(
        ["git", "blame", "-M", "-L", f"{line},{line}", "--porcelain", SRC.name],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    commit = out.split()[0]
    summary = next((l[8:] for l in out.splitlines() if l.startswith("summary ")), "")
    return commit, summary


def _flags(pattern: str, replacement: str) -> list[str]:
    flags = []
    if re.search(r"\\S|\\w|\.\*|\.\+", pattern) and "(?!" in pattern:
        flags.append("wildcard-overwrite: the match consumes an arbitrary "
                     "character and the replacement is fixed")
    if _GREEK.search(replacement) and _LATIN.search(replacement):
        flags.append("mixed-script-replacement: Greek and Latin letters in "
                     "the same output string")
    if re.fullmatch(r"[^\\()\[\]{}|*+?^$]+", pattern):
        flags.append("literal: matches a single fixed string "
                     "(document-specific, cannot generalise)")
    return flags


def _previous() -> dict[str, dict]:
    """Provenance already recorded, by pattern (keeps it stable when rules move)."""
    try:
        return {e["pattern"]: e for e in json.loads(OUT.read_text(encoding="utf-8"))}
    except (FileNotFoundError, ValueError):
        return {}


_PREV: dict[str, dict] = {}


def build() -> list[dict]:
    """Active rules get ids CS###, disabled ones DS### (same order as the lists)."""
    _PREV.update(_previous())
    entries = []
    for name, prefix, rules in (
            ("REGEX_RULES_CORPUS_SPECIFIC", "CS", ocr.REGEX_RULES_CORPUS_SPECIFIC),
            ("REGEX_RULES_CORPUS_DISABLED", "DS", ocr.REGEX_RULES_CORPUS_DISABLED)):
        entries += _build_list(name, prefix, rules)
    return entries


def _build_list(name: str, prefix: str, rules: list) -> list[dict]:
    lines = _rule_lines(name)
    assert len(lines) == len(rules), (name, len(lines), len(rules))
    entries = []
    for i, ((regex, replacement, desc), line) in enumerate(zip(rules, lines)):
        old = _PREV.get(regex.pattern)
        if old:
            commit, source = old["commit"], old["source"]
        else:
            commit, summary = _blame(line)
            source = next((lab for pre, lab in SOURCE_LABELS.items()
                           if commit.startswith(pre)), summary)
        entries.append({
            "id": f"{prefix}{i:03d}",
            "list": name,
            "pattern": regex.pattern,
            "replacement": replacement,
            "description": desc,
            "line": line,
            "commit": commit[:7],
            "source": source,
            "flags": _flags(regex.pattern, replacement),
        })
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    entries = build()
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print(f"{len(entries)} rules -> {OUT.relative_to(ROOT)}")
    if args.summary:
        by_src = collections.Counter(e["source"] for e in entries)
        print("\nBy source:")
        for s, n in by_src.most_common():
            print(f"  {n:4d}  {s}")
        by_flag = collections.Counter(f.split(":")[0] for e in entries for f in e["flags"])
        print("\nFlags:")
        for f, n in by_flag.most_common():
            print(f"  {n:4d}  {f}")
        print("\nRules with a risk flag other than 'literal':")
        for e in entries:
            fl = [f.split(":")[0] for f in e["flags"] if not f.startswith("literal")]
            if fl:
                print(f"  {e['id']} {e['pattern']!r} -> {e['replacement']!r}  {fl}")


if __name__ == "__main__":
    main()
