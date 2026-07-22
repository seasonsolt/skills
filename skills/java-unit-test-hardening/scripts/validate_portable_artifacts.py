#!/usr/bin/env python3
"""Validate portable docs/tests evidence and repository-owned schema references."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


INVALID = 2
ABSOLUTE_LOCAL_PATH = re.compile(
    r"(?P<path>"
    r"/(?:Users|home|opt|Library|Applications|Volumes|tmp|var/folders|private/(?:tmp|var))/"
    r"[^\s`)\]}>,，。；;]+"
    r"|[A-Za-z]:\\[^\s`)\]}>,，。；;]+"
    r")"
)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
INLINE_SCHEMA = re.compile(r"`(?P<target>db/schema/[^`\s]+?\.sql(?::\d+(?:-\d+)?)?)`")
PLAIN_SCHEMA = re.compile(
    r"(?<![A-Za-z0-9_./-])(?P<target>db/schema/[A-Za-z0-9_.@/-]+\.sql)"
    r"(?::\d+(?:-\d+)?)?"
)
DECLARED_SHA256 = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--docs-root", default="docs/tests", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )


def violation(path: str, kind: str, detail: str = "") -> dict[str, str]:
    item = {"path": path, "kind": kind}
    if detail:
        item["detail"] = detail
    return item


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def normalize_schema_target(raw_target: str) -> str | None:
    target = raw_target.strip("<>")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    target = unquote(parsed.path)
    target = re.sub(r"(?<=\.sql):\d+(?:-\d+)?$", "", target)
    if not target.endswith(".sql"):
        return None
    return target if "db/schema/" in target or target.startswith("db/schema/") else None


def schema_targets(line: str) -> list[str]:
    targets: list[str] = []
    for match in MARKDOWN_LINK.finditer(line):
        normalized = normalize_schema_target(match.group("target"))
        if normalized is not None:
            targets.append(normalized)
    for pattern in (INLINE_SCHEMA, PLAIN_SCHEMA):
        for match in pattern.finditer(line):
            normalized = normalize_schema_target(match.group("target"))
            if normalized is not None:
                targets.append(normalized)
    return list(dict.fromkeys(targets))


def validate(repository: Path, docs_root: Path) -> tuple[dict[str, Any], int]:
    repository = repository.resolve()
    repository_check = git(repository, "rev-parse", "--show-toplevel")
    if repository_check.returncode != 0:
        return {
            "result": "PORTABLE_EVIDENCE_INVALID",
            "message": "repository root is not a Git repository",
            "violations": [violation(".", "repository-invalid")],
        }, INVALID
    actual_root = Path(repository_check.stdout.strip()).resolve()
    if actual_root != repository:
        return {
            "result": "PORTABLE_EVIDENCE_INVALID",
            "message": "repository root does not match the Git top-level",
            "violations": [
                violation(".", "repository-root-mismatch", str(actual_root))
            ],
        }, INVALID

    resolved_docs = (
        docs_root.resolve()
        if docs_root.is_absolute()
        else (repository / docs_root).resolve()
    )
    if not inside(resolved_docs, repository) or not resolved_docs.is_dir():
        return {
            "result": "PORTABLE_EVIDENCE_INVALID",
            "message": "docs root is missing or outside the repository",
            "violations": [violation(str(docs_root), "docs-root-invalid")],
        }, INVALID

    schema_root = (repository / "db/schema").resolve()
    violations: list[dict[str, str]] = []
    checked_files: list[str] = []
    schema_sources: set[str] = set()
    validated_schema_facts: set[tuple[str, str]] = set()

    for document in sorted(resolved_docs.rglob("*.md")):
        relative_document = document.relative_to(repository).as_posix()
        checked_files.append(relative_document)
        try:
            content = document.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append(
                violation(relative_document, "document-unreadable", str(exc))
            )
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            absolute_matches = {
                match.group("path") for match in ABSOLUTE_LOCAL_PATH.finditer(line)
            }
            if str(repository) in line:
                absolute_matches.add(str(repository))
            for match in sorted(absolute_matches):
                violations.append(
                    violation(
                        relative_document,
                        "absolute-local-path",
                        f"line {line_number}: {match}",
                    )
                )

            declared_hashes = {
                match.group(0).lower() for match in DECLARED_SHA256.finditer(line)
            }
            for raw_target in schema_targets(line):
                if raw_target.startswith("db/schema/"):
                    resolved_schema = (repository / raw_target).resolve()
                else:
                    resolved_schema = (document.parent / raw_target).resolve()
                if not inside(resolved_schema, repository):
                    violations.append(
                        violation(
                            relative_document,
                            "schema-path-outside-repository",
                            f"line {line_number}: {raw_target}",
                        )
                    )
                    continue
                if not inside(resolved_schema, schema_root):
                    violations.append(
                        violation(
                            relative_document,
                            "schema-path-outside-db-schema",
                            f"line {line_number}: {raw_target}",
                        )
                    )
                    continue
                repository_relative = resolved_schema.relative_to(repository).as_posix()
                schema_sources.add(repository_relative)
                if not resolved_schema.is_file():
                    violations.append(
                        violation(
                            relative_document,
                            "schema-missing",
                            f"line {line_number}: {repository_relative}",
                        )
                    )
                    continue

                fact_key = (relative_document, repository_relative)
                if fact_key not in validated_schema_facts:
                    validated_schema_facts.add(fact_key)
                    tracked = git(
                        repository,
                        "ls-files",
                        "--error-unmatch",
                        "--",
                        repository_relative,
                    )
                    if tracked.returncode != 0:
                        violations.append(
                            violation(
                                relative_document,
                                "schema-untracked",
                                repository_relative,
                            )
                        )
                    else:
                        dirty = git(
                            repository,
                            "status",
                            "--porcelain=v1",
                            "--untracked-files=all",
                            "--",
                            repository_relative,
                        )
                        if dirty.returncode != 0 or dirty.stdout.strip():
                            violations.append(
                                violation(
                                    relative_document,
                                    "schema-dirty",
                                    repository_relative,
                                )
                            )

                actual_hash = hashlib.sha256(resolved_schema.read_bytes()).hexdigest()
                if declared_hashes and actual_hash not in declared_hashes:
                    violations.append(
                        violation(
                            relative_document,
                            "schema-hash-mismatch",
                            f"line {line_number}: {repository_relative}",
                        )
                    )

    if violations:
        return {
            "result": "PORTABLE_EVIDENCE_INVALID",
            "message": "docs/tests evidence is not portable or schema evidence is not repository-owned",
            "checked_files": checked_files,
            "schema_sources": sorted(schema_sources),
            "violations": violations,
        }, INVALID
    return {
        "result": "VALID",
        "checked_files": checked_files,
        "schema_sources": sorted(schema_sources),
    }, 0


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(f"Result: {payload['result']}")
    if "message" in payload:
        print(payload["message"])
    for item in payload.get("violations", []):
        suffix = f": {item['detail']}" if item.get("detail") else ""
        print(f"- {item['path']}: {item['kind']}{suffix}")


def main() -> int:
    args = parse_args()
    payload, exit_code = validate(
        args.repository_root.expanduser(), args.docs_root.expanduser()
    )
    emit(payload, args.format)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
