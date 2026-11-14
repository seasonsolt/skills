#!/usr/bin/env python3
"""Build anonymized judge packets: python3 -I prep_judge.py [seed]

For each sample set (1, 2) and judge (1..3): work/judge/set<k>-j<j>/<scenario>/ holds
task.md, ref.md (the held-out author sample) and five drafts labelled V..Z in a fresh
random order. Delivery notes after a '---' line are stripped. The label mapping goes
to work/judge-secret/mapping.json, outside every judge directory.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
CONDITIONS = ["direct", "stopslop", "humanizer", "humanizer-samples", "trained"]
LABELS = "VWXYZ"


def main() -> None:
    rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 20261114)
    scenarios = [s["id"] for s in json.loads((HERE / "scenarios.json").read_text())["scenarios"]]
    mapping: dict[str, dict[str, dict[str, str]]] = {}
    for k in (1, 2):
        for j in (1, 2, 3):
            name = f"set{k}-j{j}"
            mapping[name] = {}
            for sid in scenarios:
                dest = WORK / "judge" / name / sid
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy(WORK / sid / "task.md", dest / "task.md")
                shutil.copy(WORK / sid / "holdout" / "holdout.md", dest / "ref.md")
                order = CONDITIONS[:]
                rng.shuffle(order)
                mapping[name][sid] = dict(zip(LABELS, order))
                for label, cond in zip(LABELS, order):
                    text = (WORK / "out" / f"{cond}-{k}" / f"{sid}.md").read_text(encoding="utf-8")
                    text = re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)[0].strip()
                    (dest / f"{label}.md").write_text(text + "\n", encoding="utf-8")
    secret = WORK / "judge-secret"
    secret.mkdir(exist_ok=True)
    (secret / "mapping.json").write_text(json.dumps(mapping, indent=1) + "\n")
    print("packets:", len(mapping))


if __name__ == "__main__":
    main()
