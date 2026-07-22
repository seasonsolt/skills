#!/usr/bin/env python3
"""Collect today's Claude Code text messages for whitelisted work directories."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from work_roots import resolve_work_roots


SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|token|password|secret|cookie)"
        r"(\s*[:=]\s*)['\"]?[^\s'\",}]+"
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Claude Code sessions active on a local date under approved work roots."
    )
    parser.add_argument("--date", dest="day", default=date.today().isoformat())
    parser.add_argument(
        "--work-root",
        action="append",
        default=None,
        help=(
            "Approved cwd root; repeat for multiple roots. If omitted, read the "
            "OS-path-separated DAILY_REPORT_WORK_ROOTS environment variable."
        ),
    )
    parser.add_argument(
        "--claude-home",
        default=os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"),
    )
    parser.add_argument("--max-messages", type=int, default=80)
    parser.add_argument("--max-text-chars", type=int, default=4000)
    return parser.parse_args()


def local_bounds(day_text: str) -> tuple[datetime, datetime]:
    selected = date.fromisoformat(day_text)
    timezone = datetime.now().astimezone().tzinfo
    start = datetime.combine(selected, time.min, tzinfo=timezone)
    return start, start + timedelta(days=1)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def redact(text_value: str) -> str:
    redacted = text_value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    return redacted


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            value = block.get("text")
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks)


def is_under(path_text: str, roots: list[Path]) -> bool:
    try:
        candidate = Path(path_text).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def candidate_transcripts(projects: Path, roots: list[Path], start: datetime) -> list[Path]:
    """Narrow by Claude's project-folder prefix, then verify every cwd from records."""
    candidates: set[Path] = set()
    for root in roots:
        encoded_prefix = str(root).replace(os.sep, "-")
        for project_dir in projects.glob(encoded_prefix + "*"):
            if not project_dir.is_dir():
                continue
            for transcript in project_dir.rglob("*.jsonl"):
                if "subagents" in transcript.parts:
                    continue
                try:
                    if transcript.stat().st_mtime < start.timestamp():
                        continue
                except OSError:
                    continue
                candidates.add(transcript)
    return sorted(candidates)


def collect_file(
    transcript: Path,
    roots: list[Path],
    start: datetime,
    end: datetime,
    max_messages: int,
    max_text_chars: int,
) -> dict[str, Any] | None:
    session_id = transcript.stem
    cwd = ""
    branch = ""
    title = ""
    first_activity: datetime | None = None
    last_activity: datetime | None = None
    messages: list[dict[str, str]] = []

    try:
        source = transcript.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return None

    with source:
        for line in source:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(record, dict):
                continue
            if not title and isinstance(record.get("aiTitle"), str):
                title = record["aiTitle"].strip()
            if isinstance(record.get("cwd"), str) and record["cwd"]:
                cwd = record["cwd"]
            if isinstance(record.get("gitBranch"), str) and record["gitBranch"]:
                branch = record["gitBranch"]
            if isinstance(record.get("sessionId"), str) and record["sessionId"]:
                session_id = record["sessionId"]

            timestamp = parse_timestamp(record.get("timestamp"))
            if timestamp is None or not (start <= timestamp < end):
                continue
            first_activity = timestamp if first_activity is None else min(first_activity, timestamp)
            last_activity = timestamp if last_activity is None else max(last_activity, timestamp)

            record_type = record.get("type")
            if record_type not in {"user", "assistant"} or record.get("isSidechain") is True:
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            text_value = redact(extract_text(message.get("content")).strip())
            if not text_value:
                continue
            if len(text_value) > max_text_chars:
                text_value = text_value[:max_text_chars] + "…"
            messages.append(
                {
                    "role": record_type,
                    "timestamp": timestamp.isoformat(),
                    "text": text_value,
                }
            )

    if first_activity is None or not cwd or not is_under(cwd, roots):
        return None

    truncated = len(messages) > max_messages
    if truncated:
        head_count = min(4, max_messages // 4)
        messages = messages[:head_count] + messages[-(max_messages - head_count) :]

    return {
        "sessionId": session_id,
        "title": title or None,
        "cwd": str(Path(cwd).expanduser()),
        "gitBranch": branch or None,
        "firstActivityAt": first_activity.isoformat(),
        "updatedAt": last_activity.isoformat() if last_activity else None,
        "messages": messages,
        "messagesTruncated": truncated,
        "source": str(transcript),
    }


def main() -> int:
    args = parse_args()
    try:
        start, end = local_bounds(args.day)
    except ValueError as exc:
        print(json.dumps({"error": f"invalid date: {exc}"}, ensure_ascii=False))
        return 2

    try:
        roots = resolve_work_roots(args.work_root)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    claude_home = Path(args.claude_home).expanduser().resolve()
    projects = claude_home / "projects"

    sessions: list[dict[str, Any]] = []
    if projects.is_dir():
        for transcript in candidate_transcripts(projects, roots, start):
            session = collect_file(
                transcript,
                roots,
                start,
                end,
                max(1, args.max_messages),
                max(200, args.max_text_chars),
            )
            if session is not None:
                sessions.append(session)

    sessions.sort(key=lambda item: (item["updatedAt"] or "", item["sessionId"]))
    output = {
        "schemaVersion": 1,
        "date": args.day,
        "timezone": str(start.tzinfo),
        "workRoots": [str(root) for root in roots],
        "sessionCount": len(sessions),
        "sessions": sessions,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
