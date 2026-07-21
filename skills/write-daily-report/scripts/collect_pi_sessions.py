#!/usr/bin/env python3
"""Collect today's Pi Agent text messages for whitelisted work directories."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable

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
        description="Collect Pi Agent sessions active on a local date under approved work roots."
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
        "--pi-home",
        default=os.environ.get("PI_CODING_AGENT_DIR", "~/.pi/agent"),
        help="Pi Agent config directory (default: $PI_CODING_AGENT_DIR or ~/.pi/agent).",
    )
    parser.add_argument(
        "--session-dir",
        default=os.environ.get("PI_CODING_AGENT_SESSION_DIR"),
        help="Pi session directory (default: $PI_CODING_AGENT_SESSION_DIR or <pi-home>/sessions).",
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
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=datetime.now().astimezone().tzinfo)
        except (OverflowError, OSError, ValueError):
            return None
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


def read_header(transcript: Path) -> dict[str, Any] | None:
    """Read only the first non-empty JSONL record so cwd can be checked first."""
    try:
        with transcript.open("r", encoding="utf-8", errors="replace") as source:
            for line in source:
                if not line.strip():
                    continue
                record = json.loads(line)
                if (
                    isinstance(record, dict)
                    and record.get("type") == "session"
                    and isinstance(record.get("id"), str)
                    and isinstance(record.get("cwd"), str)
                ):
                    return record
                return None
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return None


def iter_session_files(session_dir: Path) -> Iterable[Path]:
    """Mirror Pi's list-all layout and skip nested pi-subagents transcripts."""
    if not session_dir.is_dir():
        return
    yield from sorted(session_dir.glob("*.jsonl"))
    try:
        project_dirs = sorted(path for path in session_dir.iterdir() if path.is_dir())
    except OSError:
        return
    for project_dir in project_dirs:
        yield from sorted(project_dir.glob("*.jsonl"))


def candidate_transcripts(
    session_dir: Path, roots: list[Path], start: datetime
) -> list[tuple[Path, dict[str, Any]]]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for transcript in iter_session_files(session_dir):
        try:
            if transcript.stat().st_mtime < start.timestamp():
                continue
        except OSError:
            continue
        header = read_header(transcript)
        if header is None or not is_under(header["cwd"], roots):
            continue
        candidates.append((transcript, header))
    return candidates


def active_branch(entries: list[dict[str, Any]], version: int) -> list[dict[str, Any]]:
    """Follow Pi's current leaf path so abandoned branches do not become facts."""
    if version < 2 or not entries:
        return entries
    indexed = {
        entry["id"]: entry
        for entry in entries
        if isinstance(entry.get("id"), str) and entry["id"]
    }
    leaf = next(
        (
            entry
            for entry in reversed(entries)
            if isinstance(entry.get("id"), str) and entry["id"] in indexed
        ),
        None,
    )
    if leaf is None:
        return entries

    path: list[dict[str, Any]] = []
    seen: set[str] = set()
    current: dict[str, Any] | None = leaf
    while current is not None:
        entry_id = current.get("id")
        if not isinstance(entry_id, str) or entry_id in seen:
            return entries
        seen.add(entry_id)
        path.append(current)
        parent_id = current.get("parentId")
        current = indexed.get(parent_id) if isinstance(parent_id, str) else None
    path.reverse()
    return path


def collect_file(
    transcript: Path,
    roots: list[Path],
    start: datetime,
    end: datetime,
    max_messages: int,
    max_text_chars: int,
    header: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    verified_header = header or read_header(transcript)
    if verified_header is None or not is_under(verified_header["cwd"], roots):
        return None

    entries: list[dict[str, Any]] = []
    try:
        source = transcript.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return None
    with source:
        for line_number, line in enumerate(source):
            if line_number == 0 and line.strip():
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(record, dict) and record.get("type") != "session":
                entries.append(record)

    try:
        version = int(verified_header.get("version", 1))
    except (TypeError, ValueError):
        version = 1
    branch_entries = active_branch(entries, version)

    title: str | None = None
    for entry in entries:
        if entry.get("type") == "session_info" and isinstance(entry.get("name"), str):
            title = entry["name"].strip() or None

    first_activity: datetime | None = None
    last_activity: datetime | None = None
    messages: list[dict[str, str]] = []
    for entry in branch_entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        timestamp = parse_timestamp(message.get("timestamp")) or parse_timestamp(entry.get("timestamp"))
        if timestamp is None or not (start <= timestamp < end):
            continue
        text_value = redact(extract_text(message.get("content")).strip())
        if not text_value:
            continue
        first_activity = timestamp if first_activity is None else min(first_activity, timestamp)
        last_activity = timestamp if last_activity is None else max(last_activity, timestamp)
        if len(text_value) > max_text_chars:
            text_value = text_value[:max_text_chars] + "…"
        messages.append(
            {
                "role": role,
                "timestamp": timestamp.isoformat(),
                "text": text_value,
            }
        )

    if first_activity is None:
        return None

    truncated = len(messages) > max_messages
    if truncated:
        head_count = min(4, max_messages // 4)
        messages = messages[:head_count] + messages[-(max_messages - head_count) :]

    parent_session = verified_header.get("parentSession")
    return {
        "sessionId": verified_header["id"],
        "title": title,
        "cwd": str(Path(verified_header["cwd"]).expanduser()),
        "gitBranch": None,
        "parentSession": parent_session if isinstance(parent_session, str) else None,
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
    pi_home = Path(args.pi_home).expanduser().resolve()
    session_dir = (
        Path(args.session_dir).expanduser().resolve()
        if args.session_dir
        else pi_home / "sessions"
    )

    sessions: list[dict[str, Any]] = []
    for transcript, header in candidate_transcripts(session_dir, roots, start):
        session = collect_file(
            transcript,
            roots,
            start,
            end,
            max(1, args.max_messages),
            max(200, args.max_text_chars),
            header,
        )
        if session is not None:
            sessions.append(session)

    sessions.sort(key=lambda item: (item["updatedAt"] or "", item["sessionId"]))
    output = {
        "schemaVersion": 1,
        "date": args.day,
        "timezone": str(start.tzinfo),
        "workRoots": [str(root) for root in roots],
        "sessionDir": str(session_dir),
        "sessionCount": len(sessions),
        "sessions": sessions,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
