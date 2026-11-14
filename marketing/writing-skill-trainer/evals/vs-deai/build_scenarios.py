#!/usr/bin/env python3
"""Build scenarios.json and the per-scenario work files for the de-AI-skill comparison.

Chinese scenarios are reused from ../../data/scenarios.json. The English scenario is
cut from public-domain Mark Twain essays; pass the directory holding the downloaded
texts (see README.md, "复现") as the only argument.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / "data" / "scenarios.json"
REUSED = {"restrained-satire": "nonspace", "tech-news": "nonspace"}
PD = "Public Domain (US); Mark Twain, d. 1910"
TWAIN = [
    ("train", "On the Decay of the Art of Lying", "pg2572.txt",
     "https://www.gutenberg.org/ebooks/2572", "Observe, I do not mean to suggest"),
    ("train", "Taming the Bicycle", "Taming_the_Bicycle.txt.json",
     "https://en.wikisource.org/wiki/Taming_the_Bicycle", "I thought the matter over"),
    ("train", "The Danger of Lying in Bed", "The_Danger_of_Lying_in_Bed.txt.json",
     "https://en.wikisource.org/wiki/The_Danger_of_Lying_in_Bed", "The man in the ticket-office"),
    ("holdout", "How to Tell a Story", "pg3250.txt",
     "https://www.gutenberg.org/ebooks/3250", "I do not claim that I can tell a story"),
]
TWAIN_PROMPT = """Write a humorous first-person essay of 450-650 words from the fictional \
material below. Do not copy sentences from any published work. Do not add facts, \
numbers, people or quotations beyond the material.

Material: The narrator, aged fifty-one, bought a motorized "smart" standing desk on \
his doctor's advice. It cost 640 dollars. The desk is controlled by an app; the app \
requires an account, and the account requires a password of at least 14 characters. \
On the first morning the desk rose to its full height of 48 inches and would not \
come down for three days. During those three days the narrator answered his \
correspondence standing on a kitchen chair. The company's help line told him to \
"restart the furniture". His neighbor Mrs. Abernathy, a retired schoolteacher, \
fixed the desk by pulling the plug out and putting it back. The narrator now works \
at the desk sitting down, at its lowest setting. His doctor has asked how the \
standing is going, and he has answered that it is going well."""


def load_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        page = next(iter(json.loads(raw)["query"]["pages"].values()))
        return page["extract"]
    return raw.replace("\r\n", "\n")


def excerpt(text: str, start: str, words: int = 900) -> str:
    """Whole paragraphs from the one containing `start`, up to about `words` words."""
    text = text[text.index(start):]
    text = re.split(r"\*\*\* ?END OF", text)[0]
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    out: list[str] = []
    for para in filter(None, paras):
        if sum(len(p.split()) for p in out) + len(para.split()) > words and out:
            break
        out.append(para)
    return "\n\n".join(out)


def twain_scenario(raw_dir: Path) -> dict:
    sources = []
    for role, title, name, url, start in TWAIN:
        text = excerpt(load_text(raw_dir / name), start)
        sources.append({
            "title": f"Mark Twain, {title}", "url": url, "license": PD, "role": role,
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text,
        })
    return {
        "id": "twain-essay", "name": "English humorous essay", "language": "en",
        "length": [450, 650], "length_unit": "words", "writing_prompt": TWAIN_PROMPT,
        "training_sources": [s for s in sources if s["role"] == "train"],
        "style_holdout": next(s for s in sources if s["role"] == "holdout"),
    }


def main() -> None:
    base = {s["id"]: s for s in json.loads(BASE.read_text(encoding="utf-8"))["scenarios"]}
    scenarios = []
    for sid, unit in REUSED.items():
        s = base[sid]
        lo, hi = (int(n) for n in re.findall(r"\d+", s["writing_prompt"])[:2])
        scenarios.append({
            "id": sid, "name": s["name"], "language": "zh", "length": [lo, hi],
            "length_unit": unit, "writing_prompt": s["writing_prompt"],
            "training_sources": s["training_sources"], "style_holdout": s["style_holdout"],
        })
    scenarios.append(twain_scenario(Path(sys.argv[1])))
    (HERE / "scenarios.json").write_text(
        json.dumps({"scenarios": scenarios}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    prompts = []
    for s in scenarios:
        root = HERE / "work" / s["id"]
        (root / "train").mkdir(parents=True, exist_ok=True)
        (root / "holdout").mkdir(exist_ok=True)
        (root / "task.md").write_text(s["writing_prompt"] + "\n", encoding="utf-8")
        for i, src in enumerate(s["training_sources"], 1):
            (root / "train" / f"sample-{i}.md").write_text(
                f"# {src['title']}\n\n{src['text']}\n", encoding="utf-8")
        hold = s["style_holdout"]
        (root / "holdout" / "holdout.md").write_text(
            f"# {hold['title']}\n\n{hold['text']}\n", encoding="utf-8")
        prompts.append({
            "id": s["id"], "task": s["writing_prompt"], "materials": [],
            "length": s["length"], "length_unit": s["length_unit"],
        })
        print(s["id"], s["length"], [len(x["text"]) for x in s["training_sources"]])
    (HERE / "prompts.json").write_text(
        json.dumps(prompts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
