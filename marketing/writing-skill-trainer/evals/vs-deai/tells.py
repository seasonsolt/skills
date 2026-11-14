#!/usr/bin/env python3
"""Crude count of generic-AI tells, built from the two de-AI skills' own lists.

Usage: python3 -I tells.py work/out   (prints one JSON line per draft)

This is the de-AI skills' home metric. A regex cannot tell a justified use from an
empty one, so read the numbers as a rough density, not a verdict.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ZH = {
    "假对比": r"不仅仅?是[^。]{0,30}(?:更是|而是|还是)|不是[^。，]{0,20}，?而是",
    "高频词": r"赋能|至关重要|深入探讨|无缝|闭环|彰显|凸显|助力|格局|见证|不可或缺",
    "套话收尾": r"总而言之|综上所述|总的来说|拭目以待|未来可期|值得期待|让我们",
    "起跑铺垫": r"值得注意的是|需要指出的是|不可否认|众所周知|毋庸置疑|随着[^。，]{0,20}的发展",
    "破折号": r"——",
    "格言腔": r"或许，?这就是|这就是[^。]{0,12}的(?:意义|力量|真相)|真正的[^。，]{1,10}(?:是|在于)",
}
EN = {
    "throat_clearing": r"\bhere's (?:the thing|what|why|this|that)|\bit turns out\b"
    r"|\bthe truth is\b|\blet me be clear\b|\bat its core\b|\bit's worth noting\b"
    r"|\bat the end of the day\b|\bwhen it comes to\b|\bin a world where\b"
    r"|\bthe reality is\b|\bmake no mistake\b|\blet that sink in\b",
    "binary_contrast": r"\b(?:isn't|is not|wasn't|was not|not) (?:just |only |about )?"
    r"[^.;]{1,40}[,;—-]+ ?(?:it's|it is|it was|but) ",
    "adverbs": r"\b(?:really|just|literally|genuinely|honestly|simply|actually|deeply"
    r"|truly|fundamentally|inherently|inevitably|interestingly|importantly|crucially)\b",
    "em_dash": r"—|--",
    "jargon": r"\b(?:navigate|unpack|lean into|landscape|game-changer|double down"
    r"|deep dive|moving forward|circle back)\b",
}


def body(text: str) -> str:
    text = re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)[0]
    return re.sub(r"^#.*$", "", text, flags=re.M)


def count(path: Path) -> dict:
    text = body(path.read_text(encoding="utf-8"))
    english = len(re.findall(r"[A-Za-z]", text)) > len(text) / 2
    pats, size = (EN, len(text.split())) if english else (ZH, len(re.sub(r"\s", "", text)))
    hits = {k: len(re.findall(p, text, flags=re.I)) for k, p in pats.items()}
    total = sum(hits.values())
    return {
        "draft": f"{path.parent.name}/{path.name}", "size": size, "tells": total,
        "per_1000": round(total * 1000 / max(size, 1), 1),
        "by_type": {k: v for k, v in hits.items() if v},
    }


if __name__ == "__main__":
    for f in sorted(Path(sys.argv[1]).glob("*/*.md")):
        print(json.dumps(count(f), ensure_ascii=False))
