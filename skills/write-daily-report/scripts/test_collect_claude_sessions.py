#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("collect_claude_sessions.py")
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("collect_claude_sessions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CollectClaudeSessionsTest(unittest.TestCase):
    def test_redacts_credentials(self) -> None:
        value = collector.redact("api_key=abc123 Bearer secret-token password:guessme")
        self.assertNotIn("abc123", value)
        self.assertNotIn("secret-token", value)
        self.assertNotIn("guessme", value)
        self.assertEqual(value.count("[REDACTED]"), 3)

    def test_collects_only_text_for_whitelisted_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "workspaces" / "company"
            work_cwd = work_root / "service"
            work_cwd.mkdir(parents=True)
            transcript = base / "session.jsonl"
            timestamp = datetime.now().astimezone().isoformat()
            records = [
                {
                    "type": "user",
                    "timestamp": timestamp,
                    "cwd": str(work_cwd),
                    "sessionId": "session-1",
                    "gitBranch": "feature/test",
                    "message": {"content": "修复订单测试，token=private-value"},
                },
                {
                    "type": "assistant",
                    "timestamp": timestamp,
                    "cwd": str(work_cwd),
                    "sessionId": "session-1",
                    "message": {
                        "content": [
                            {"type": "thinking", "thinking": "private reasoning"},
                            {"type": "text", "text": "新增 4 条测试并全部通过"},
                            {"type": "tool_use", "name": "Bash", "input": {"command": "secret"}},
                        ]
                    },
                },
            ]
            transcript.write_text(
                "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
                encoding="utf-8",
            )
            start, end = collector.local_bounds(date.today().isoformat())
            result = collector.collect_file(transcript, [work_root.resolve()], start, end, 20, 1000)

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["sessionId"], "session-1")
            combined = "\n".join(message["text"] for message in result["messages"])
            self.assertIn("新增 4 条测试并全部通过", combined)
            self.assertIn("[REDACTED]", combined)
            self.assertNotIn("private reasoning", combined)
            self.assertNotIn("tool_use", combined)

    def test_rejects_cwd_outside_work_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "work"
            work_root.mkdir()
            outside = base / "personal"
            outside.mkdir()
            transcript = base / "outside.jsonl"
            timestamp = datetime.now().astimezone().isoformat()
            transcript.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": timestamp,
                        "cwd": str(outside),
                        "message": {"content": "写小红书文案"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            start, end = collector.local_bounds(date.today().isoformat())
            result = collector.collect_file(transcript, [work_root.resolve()], start, end, 20, 1000)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
