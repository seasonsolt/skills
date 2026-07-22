#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("collect_pi_sessions.py")
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("collect_pi_sessions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


class CollectPiSessionsTest(unittest.TestCase):
    def test_redacts_credentials(self) -> None:
        value = collector.redact("api_key=abc123 Bearer secret-token password:guessme")
        self.assertNotIn("abc123", value)
        self.assertNotIn("secret-token", value)
        self.assertNotIn("guessme", value)
        self.assertEqual(value.count("[REDACTED]"), 3)

    def test_collects_active_branch_text_and_ignores_private_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "workspaces" / "company"
            work_cwd = work_root / "service"
            work_cwd.mkdir(parents=True)
            transcript = base / "session.jsonl"
            timestamp = datetime.now().astimezone()
            timestamp_ms = int(timestamp.timestamp() * 1000)
            records = [
                {
                    "type": "session",
                    "version": 3,
                    "id": "session-1",
                    "timestamp": timestamp.isoformat(),
                    "cwd": str(work_cwd),
                    "parentSession": "/tmp/parent.jsonl",
                },
                {
                    "type": "message",
                    "id": "user-root",
                    "parentId": None,
                    "timestamp": timestamp.isoformat(),
                    "message": {
                        "role": "user",
                        "timestamp": timestamp_ms,
                        "content": [{"type": "text", "text": "修复订单测试，token=private"}],
                    },
                },
                {
                    "type": "message",
                    "id": "abandoned",
                    "parentId": "user-root",
                    "timestamp": timestamp.isoformat(),
                    "message": {
                        "role": "assistant",
                        "timestamp": timestamp_ms,
                        "content": [{"type": "text", "text": "旧分支错误结论"}],
                    },
                },
                {
                    "type": "message",
                    "id": "active",
                    "parentId": "user-root",
                    "timestamp": timestamp.isoformat(),
                    "message": {
                        "role": "assistant",
                        "timestamp": timestamp_ms,
                        "content": [
                            {"type": "thinking", "thinking": "private reasoning"},
                            {"type": "text", "text": "新增 4 条测试并全部通过"},
                            {"type": "toolCall", "name": "bash", "arguments": {"cmd": "secret"}},
                        ],
                    },
                },
                {
                    "type": "message",
                    "id": "tool-result",
                    "parentId": "active",
                    "timestamp": timestamp.isoformat(),
                    "message": {
                        "role": "toolResult",
                        "timestamp": timestamp_ms,
                        "content": [{"type": "text", "text": "raw tool output"}],
                    },
                },
                {
                    "type": "session_info",
                    "id": "named",
                    "parentId": "tool-result",
                    "timestamp": timestamp.isoformat(),
                    "name": "订单测试加固",
                },
            ]
            write_jsonl(transcript, records)
            start, end = collector.local_bounds(date.today().isoformat())
            result = collector.collect_file(transcript, [work_root.resolve()], start, end, 20, 1000)

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["sessionId"], "session-1")
            self.assertEqual(result["title"], "订单测试加固")
            self.assertEqual(result["parentSession"], "/tmp/parent.jsonl")
            combined = "\n".join(message["text"] for message in result["messages"])
            self.assertIn("新增 4 条测试并全部通过", combined)
            self.assertIn("[REDACTED]", combined)
            self.assertNotIn("旧分支错误结论", combined)
            self.assertNotIn("private reasoning", combined)
            self.assertNotIn("raw tool output", combined)

    def test_rejects_outside_cwd_before_collecting_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "work"
            work_root.mkdir()
            outside = base / "personal"
            outside.mkdir()
            transcript = base / "outside.jsonl"
            timestamp = datetime.now().astimezone().isoformat()
            write_jsonl(
                transcript,
                [
                    {
                        "type": "session",
                        "version": 3,
                        "id": "outside",
                        "timestamp": timestamp,
                        "cwd": str(outside),
                    },
                    {
                        "type": "message",
                        "id": "m1",
                        "parentId": None,
                        "timestamp": timestamp,
                        "message": {"role": "user", "content": "写个人内容"},
                    },
                ],
            )
            start, end = collector.local_bounds(date.today().isoformat())
            result = collector.collect_file(transcript, [work_root.resolve()], start, end, 20, 1000)
            self.assertIsNone(result)

    def test_filters_messages_to_selected_local_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "work"
            work_root.mkdir()
            transcript = base / "session.jsonl"
            now = datetime.now().astimezone()
            yesterday = now - timedelta(days=1)
            write_jsonl(
                transcript,
                [
                    {
                        "type": "session",
                        "version": 3,
                        "id": "cross-day",
                        "timestamp": yesterday.isoformat(),
                        "cwd": str(work_root),
                    },
                    {
                        "type": "message",
                        "id": "old",
                        "parentId": None,
                        "timestamp": yesterday.isoformat(),
                        "message": {"role": "user", "content": "昨天的工作"},
                    },
                    {
                        "type": "message",
                        "id": "today",
                        "parentId": "old",
                        "timestamp": now.isoformat(),
                        "message": {"role": "assistant", "content": "今天新增的结果"},
                    },
                ],
            )
            start, end = collector.local_bounds(date.today().isoformat())
            result = collector.collect_file(transcript, [work_root.resolve()], start, end, 20, 1000)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual([item["text"] for item in result["messages"]], ["今天新增的结果"])

    def test_session_discovery_skips_nested_subagent_transcripts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions = Path(temp_dir) / "sessions"
            project = sessions / "--project--"
            nested = project / "parent-session" / "run-1"
            nested.mkdir(parents=True)
            (project / "main.jsonl").write_text("", encoding="utf-8")
            (nested / "subagent.jsonl").write_text("", encoding="utf-8")

            discovered = list(collector.iter_session_files(sessions))
            self.assertEqual(discovered, [project / "main.jsonl"])


if __name__ == "__main__":
    unittest.main()
