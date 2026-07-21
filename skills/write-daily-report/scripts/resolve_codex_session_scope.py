#!/usr/bin/env python3
"""Resolve whether Codex thread cwd values belong to approved work projects."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from work_roots import resolve_work_roots


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify Codex cwd values using direct roots and verified Codex worktrees."
    )
    parser.add_argument("--cwd", action="append", required=True)
    parser.add_argument(
        "--work-root",
        action="append",
        default=None,
        help=(
            "Approved source root; repeat for multiple roots. If omitted, read the "
            "OS-path-separated DAILY_REPORT_WORK_ROOTS environment variable."
        ),
    )
    parser.add_argument(
        "--codex-worktrees-root",
        default="~/.codex/worktrees",
    )
    return parser.parse_args()


def canonical(value: str) -> Path:
    return Path(value).expanduser().resolve()


def is_under(candidate: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def git_source_root(worktree: Path) -> tuple[Path | None, str | None]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(worktree),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)

    if completed.returncode != 0:
        message = completed.stderr.strip() or "git rev-parse failed"
        return None, message
    output = completed.stdout.strip()
    if not output:
        return None, "git common-dir is empty"
    common_dir = canonical(output)
    if common_dir.name != ".git":
        return None, f"unsupported git common-dir: {common_dir}"
    return common_dir.parent, None


def resolve_scope(cwd_value: str, work_roots: list[Path], codex_root: Path) -> dict[str, Any]:
    cwd = canonical(cwd_value)
    base: dict[str, Any] = {
        "cwd": str(cwd),
        "included": False,
        "mode": "excluded",
        "sourceRoot": None,
        "reason": None,
    }

    if is_under(cwd, work_roots):
        base.update(
            included=True,
            mode="direct",
            sourceRoot=str(cwd),
            reason="cwd is under an approved work root",
        )
        return base

    if not is_under(cwd, [codex_root]):
        base["reason"] = "cwd is outside approved roots and Codex worktrees"
        return base
    if not cwd.is_dir():
        base["reason"] = "Codex worktree cwd does not exist"
        return base

    source_root, error = git_source_root(cwd)
    if source_root is None:
        base["reason"] = error or "unable to resolve Git source root"
        return base
    base["sourceRoot"] = str(source_root)
    if not is_under(source_root, work_roots):
        base["reason"] = "Codex worktree source repository is outside approved roots"
        return base

    base.update(
        included=True,
        mode="codex_worktree",
        reason="Git common-dir source repository is under an approved work root",
    )
    return base


def main() -> int:
    args = parse_args()
    try:
        work_roots = resolve_work_roots(args.work_root)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    codex_root = canonical(args.codex_worktrees_root)
    results = [resolve_scope(value, work_roots, codex_root) for value in dict.fromkeys(args.cwd)]
    json.dump(
        {
            "schemaVersion": 1,
            "workRoots": [str(root) for root in work_roots],
            "codexWorktreesRoot": str(codex_root),
            "results": results,
        },
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
