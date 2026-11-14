"""Tests for precheck.py exit codes and per-draft checks (synthetic fixtures only)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("precheck.py")
MATERIAL = "素材：耳机用了三周，续航8小时。"


def prompt(**extra: str) -> dict:
    base = {"id": "P1", "task": "写一段评测", "materials": [MATERIAL]}
    return {**base, "length": [10, 40], **extra}


class PrecheckTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.prompts = self.root / "prompts.json"
        self.write_prompts([prompt()])
        self.drafts = self.root / "s1"
        self.drafts.mkdir()

    def write_prompts(self, prompts: list[dict]) -> None:
        text = json.dumps(prompts, ensure_ascii=False)
        self.prompts.write_text(text, encoding="utf-8")

    def run_precheck(
        self, *drafts: Path, corpus: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-I", str(SCRIPT), "--prompts", str(self.prompts)]
        if corpus:
            cmd += ["--corpus", str(corpus), "--ngram", "6"]
        cmd += [str(d) for d in drafts]
        return subprocess.run(cmd, capture_output=True, text=True)

    def draft(self, text: str, name: str = "P1.md") -> None:
        (self.drafts / name).write_text(text, encoding="utf-8")

    def test_clean_draft_passes_and_ignores_delivery_note(self) -> None:
        note = "\n---\n交付说明：补了 99 个缺口。"
        self.draft("# 标题\n用了三周，续航8小时，比上一副耐用。" + note)
        res = self.run_precheck(self.drafts)
        self.assertEqual(res.returncode, 0, res.stderr)
        row = json.loads(res.stdout)
        self.assertTrue(row["length_ok"])
        self.assertEqual(row["new_numbers"], [])

    def test_new_number_or_title_fails(self) -> None:
        self.draft("用了三周，续航8小时，售价399元，适合听《无名曲》的人。")
        res = self.run_precheck(self.drafts)
        self.assertEqual(res.returncode, 1)
        row = json.loads(res.stdout)
        self.assertEqual(row["new_numbers"], ["399"])
        self.assertEqual(row["new_titles"], ["无名曲"])

    def test_length_out_of_range_fails(self) -> None:
        self.draft("续航8小时。")
        res = self.run_precheck(self.drafts)
        self.assertEqual(res.returncode, 1)
        self.assertFalse(json.loads(res.stdout)["length_ok"])

    def test_corpus_overlap_is_reported(self) -> None:
        corpus = self.root / "corpus"
        corpus.mkdir()
        shared = "低频下潜很深但是收得很快"
        (corpus / "a.md").write_text("这副耳机的" + shared, encoding="utf-8")
        self.draft("用了三周，续航8小时，" + shared + "。")
        res = self.run_precheck(self.drafts, corpus=corpus)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(shared, json.loads(res.stdout)["corpus_overlap"])

    def test_unusable_inputs_exit_2(self) -> None:
        self.draft("用了三周，续航8小时，比上一副耐用。")
        cases = {
            "file instead of dir": [self.drafts / "P1.md"],
            "missing dir": [self.root / "nope"],
        }
        for label, args in cases.items():
            with self.subTest(label):
                self.assertEqual(self.run_precheck(*args).returncode, 2)
        with self.subTest("unknown prompt id"):
            self.draft("用了三周，续航8小时。", name="P9.md")
            self.assertEqual(self.run_precheck(self.drafts).returncode, 2)
        with self.subTest("unknown length_unit"):
            (self.drafts / "P9.md").unlink()
            self.write_prompts([prompt(length_unit="lines")])
            self.assertEqual(self.run_precheck(self.drafts).returncode, 2)


if __name__ == "__main__":
    unittest.main()
