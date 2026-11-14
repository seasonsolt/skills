#!/usr/bin/env python3
"""Unblind the judge verdicts and write results.json: python3 -I aggregate.py

Per scenario and condition: mean voice rank and mean overall rank (1 = best of 5)
over 2 sample sets x 3 judges, how often the trained-skill draft is ranked above
each other condition, and how many drafts a majority of judges (>= 2 of 3) flagged
for a fact violation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
CONDITIONS = ["direct", "stopslop", "humanizer", "humanizer-samples", "trained"]


def similarity() -> dict:
    """difflib ratio between each humanizer-zh rewrite and the draft it started from."""
    out: dict[str, dict[str, list[float]]] = {}
    for cond in ("humanizer", "humanizer-samples"):
        out[cond] = {}
        for src in sorted((WORK / "out" / "direct-1").glob("*.md")):
            out[cond][src.stem] = [
                round(SequenceMatcher(
                    None,
                    (WORK / "out" / f"direct-{k}" / src.name).read_text(encoding="utf-8"),
                    (WORK / "out" / f"{cond}-{k}" / src.name).read_text(encoding="utf-8"),
                ).ratio(), 2)
                for k in (1, 2)
            ]
    return out


def main() -> None:
    mapping = json.loads((WORK / "judge-secret" / "mapping.json").read_text())
    ranks = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    flags = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    beats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for packet, scenarios in mapping.items():
        k = packet.split("-")[0]
        verdicts = json.loads((WORK / "judge" / packet / "verdicts.json").read_text())
        for sid, labels in scenarios.items():
            v = verdicts[sid]
            for key in ("voice_ranking", "overall_ranking"):
                order = [labels[x] for x in v[key]]
                assert sorted(order) == sorted(CONDITIONS), (packet, sid, key)
                for pos, cond in enumerate(order, 1):
                    ranks[sid][key][cond].append(pos)
                for cond in CONDITIONS[:-1]:
                    if order.index("trained") < order.index(cond):
                        beats[sid][key][cond] += 1
            for label, items in v.get("fact_violations", {}).items():
                if items:
                    flags[sid][labels[label]][k] += 1
    out = {"judgments_per_cell": 6, "scenarios": {}}
    for sid in ranks:
        cell = {}
        for cond in CONDITIONS:
            voice, overall = (ranks[sid][key][cond] for key in ("voice_ranking", "overall_ranking"))
            cell[cond] = {
                "voice_rank_mean": round(sum(voice) / len(voice), 2),
                "voice_first": voice.count(1),
                "overall_rank_mean": round(sum(overall) / len(overall), 2),
                "overall_first": overall.count(1),
                "drafts_flagged_by_majority": sum(n >= 2 for n in flags[sid][cond].values()),
            }
        out["scenarios"][sid] = {
            "conditions": cell,
            "trained_ranked_above": {
                key: {c: beats[sid][key][c] for c in CONDITIONS[:-1]}
                for key in ("voice_ranking", "overall_ranking")
            },
        }
    out["similarity_to_direct_draft"] = similarity()
    (HERE / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for sid, data in out["scenarios"].items():
        print(f"\n{sid}")
        for cond, c in data["conditions"].items():
            print(f"  {cond:18} voice {c['voice_rank_mean']:.2f} (#1 x{c['voice_first']})  "
                  f"overall {c['overall_rank_mean']:.2f} (#1 x{c['overall_first']})  "
                  f"fact-flagged drafts {c['drafts_flagged_by_majority']}/2")
        print("  trained above:", data["trained_ranked_above"])


if __name__ == "__main__":
    main()
