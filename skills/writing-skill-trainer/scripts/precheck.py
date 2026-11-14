#!/usr/bin/env python3
"""Mechanical checks that run before any blind judging (writing-skill-trainer Phase 3).

Usage:
  python3 -I precheck.py --prompts <skill-dir>/evals/test-prompts.json \
      --corpus <training-corpus-dir> <drafts-dir> [<drafts-dir> ...]

Each drafts dir holds <prompt-id>.md files, one dir per sample (v2/s1, v2/s2, ...).
Text after a line that is exactly '---' (the delivery note) is ignored. One JSON
line per draft:
  chars / length_ok  length in the prompt's `length_unit` (default: all
                     non-whitespace characters, Markdown heading lines excluded);
                     window = length range +/-10%
  new_numbers        numbers absent from task + materials (list numbering ignored)
  new_titles         《》 titles absent from task + materials
  corpus_overlap     runs of >= --ngram chars (punctuation ignored) shared with
                     the training corpus
Exit code 1 when any draft fails length or adds numbers/titles, so callers can gate
judging. Exit code 2 when the inputs are unusable: a drafts dir is missing or has
no drafts, a .md file matches no prompt id, or a prompt has an unknown
`length_unit` (skipping these silently would look like a pass). Arithmetic derived
from given numbers (e.g. a score difference) is still reported; a judge decides
whether it is a new fact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

UNITS = {
    # every non-whitespace character, including Latin letters and digits
    "nonspace": lambda t: len(re.sub(r"\s", "", t)),
    # CJK ideographs plus full-width punctuation (Word's "中文字符")
    "cjk_punct": lambda t: len(
        re.findall(r"[一-鿿　-〿＀-￯]", t)
    ),
    # whitespace-separated words, for English prompts
    "words": lambda t: len(t.split()),
}
LIST_MARKER = re.compile(r"^\s*(?:[-*]\s*)?\d+(?:\.\d+)*[.、：:)]\s*", re.M)


def body(text: str) -> str:
    return re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)[0]


def norm(text: str) -> str:
    return re.sub(r"[\s\W_]", "", text)


def overlap(text: str, corpus: list[str], grams: set[str], n: int) -> list[str]:
    """Maximal runs of >= n normalized chars that also occur in a corpus article."""
    t, hits, i = norm(text), [], 0
    while i <= len(t) - n:
        if t[i : i + n] not in grams:
            i += 1
            continue
        j = i + n
        while j < len(t) and any(t[i : j + 1] in d for d in corpus):
            j += 1
        hits.append(t[i:j])
        i = j
    return hits


def check(path: Path, prompt: dict, corpus: list[str], grams: set[str], n: int) -> dict:
    text = body(path.read_text(encoding="utf-8"))
    given = prompt.get("task", "") + "".join(prompt.get("materials", []))
    unit = prompt.get("length_unit", "nonspace")
    chars = UNITS[unit](re.sub(r"^#.*$", "", text, flags=re.M))
    lo, hi = prompt["length"]
    numbers = re.findall(r"\d+(?:\.\d+)?", LIST_MARKER.sub("", text))
    return {
        "draft": str(path),
        "chars": chars,
        "length_unit": unit,
        "length_ok": lo * 0.9 <= chars <= hi * 1.1,
        "new_numbers": sorted({m for m in numbers if m not in given}),
        "new_titles": sorted(
            {m for m in re.findall(r"《([^》]+)》", text) if m not in given}
        ),
        "corpus_overlap": overlap(text, corpus, grams, n) if corpus else [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--prompts", required=True, type=Path)
    ap.add_argument("--corpus", type=Path, help="training articles dir (*.md, *.txt)")
    ap.add_argument("--ngram", type=int, default=12)
    ap.add_argument("drafts", nargs="+", type=Path)
    args = ap.parse_args()

    prompts = json.loads(args.prompts.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in prompts}
    corpus: list[str] = []
    if args.corpus:
        corpus = [
            norm(p.read_text(encoding="utf-8"))
            for p in sorted(args.corpus.rglob("*"))
            if p.suffix in {".md", ".txt"}
        ]
    n = args.ngram
    grams = {d[i : i + n] for d in corpus for i in range(len(d) - n + 1)}

    errors = [
        f"{p['id']}: unknown length_unit {p['length_unit']!r}"
        for p in prompts
        if p.get("length_unit", "nonspace") not in UNITS
    ]
    for drafts in args.drafts:
        files = sorted(drafts.glob("*.md"))
        if not files:
            errors.append(f"{drafts}: no .md drafts found")
        errors += [
            f"{f}: no prompt with id {f.stem!r}" for f in files if f.stem not in by_id
        ]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2

    failed = False
    for drafts in args.drafts:
        for f in sorted(drafts.glob("*.md")):
            prompt = by_id[f.stem]
            res = check(f, prompt, corpus, grams, n)
            added = res["new_numbers"] or res["new_titles"]
            failed |= not res["length_ok"] or bool(added)
            print(json.dumps(res, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
