#!/usr/bin/env python3
"""Run the repository's portable checks."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by the setup contract
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc


ROOT = Path(__file__).resolve().parents[1]
INLINE_LINK = re.compile(
    r"!?\[[^\]]*\]\(\s*(<[^>\n]+>|[^)\s]+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>\n]+>|\S+)", re.MULTILINE)
SKILL_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / path.decode() for path in result.stdout.split(b"\0") if path]


def check_skill(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return [f"{path.relative_to(ROOT)}: missing YAML frontmatter"]
    try:
        end = lines.index("---", 1)
        data = yaml.safe_load("\n".join(lines[1:end]))
    except (ValueError, yaml.YAMLError) as exc:
        return [f"{path.relative_to(ROOT)}: invalid YAML frontmatter: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.relative_to(ROOT)}: frontmatter must be a mapping"]
    errors = [
        f"{path.relative_to(ROOT)}: frontmatter {key!r} must be a non-empty string"
        for key in ("name", "description")
        if not isinstance(data.get(key), str) or not data[key].strip()
    ]
    errors.extend(
        f"{path.relative_to(ROOT)}: unexpected frontmatter key {key!r}"
        for key in sorted(data.keys() - SKILL_KEYS)
    )
    name = data.get("name")
    if isinstance(name, str) and not SKILL_NAME.fullmatch(name):
        errors.append(f"{path.relative_to(ROOT)}: invalid skill name {name!r}")
    return errors


def check_openai_yaml(path: Path) -> list[str]:
    rel = path.relative_to(ROOT)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"{rel}: invalid YAML: {exc}"]
    interface = data.get("interface") if isinstance(data, dict) else None
    if not isinstance(interface, dict):
        return [f"{rel}: interface must be a mapping"]
    errors = [
        f"{rel}: interface.{key} must be a non-empty string"
        for key in ("display_name", "short_description", "default_prompt")
        if not isinstance(interface.get(key), str) or not interface[key].strip()
    ]
    short = interface.get("short_description")
    if isinstance(short, str) and not 25 <= len(short) <= 64:
        errors.append(f"{rel}: interface.short_description must be 25-64 characters")
    skill_name = path.parent.parent.name
    prompt = interface.get("default_prompt")
    if isinstance(prompt, str) and f"${skill_name}" not in prompt:
        errors.append(f"{rel}: interface.default_prompt must mention ${skill_name}")
    return errors


def check_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = []
    for match in (*INLINE_LINK.finditer(text), *REFERENCE_LINK.finditer(text)):
        target = match.group(1).strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
            continue
        linked = path.parent / unquote(parsed.path)
        if not linked.exists():
            line = text.count("\n", 0, match.start()) + 1
            errors.append(f"{path.relative_to(ROOT)}:{line}: missing link target {target!r}")
    return errors


def run(label: str, command: list[str]) -> bool:
    print(f"==> {label}", flush=True)
    return subprocess.run(command, cwd=ROOT).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="skip the slow Java skill tests")
    quick = parser.parse_args().quick
    files = repository_files()
    errors: list[str] = []

    for path in files:
        try:
            if path.name == "SKILL.md":
                errors.extend(check_skill(path))
            if path.name == "openai.yaml" and path.parent.name == "agents":
                errors.extend(check_openai_yaml(path))
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".md":
                errors.extend(check_markdown(path))
            elif path.suffix == ".py":
                compile(path.read_bytes(), str(path), "exec")
        except (UnicodeDecodeError, json.JSONDecodeError, SyntaxError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    ruby_files = [str(path.relative_to(ROOT)) for path in files if path.suffix == ".rb"]
    if ruby_files and not shutil.which("ruby"):
        errors.append("Ruby is required to syntax-check .rb files")
    for path in ruby_files:
        if not run(f"ruby -c {path}", ["ruby", "-c", path]):
            errors.append(f"{path}: Ruby syntax check failed")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    tests_ok = run(
        "write-daily-report tests",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "skills/write-daily-report/scripts",
            "-p",
            "test_*.py",
        ],
    )
    if not quick:
        tests_ok = run(
            "java-unit-test-hardening tests",
            [sys.executable, "-m", "pytest", "skills/java-unit-test-hardening/tests", "-q"],
        ) and tests_ok

    if tests_ok:
        print(f"All checks passed{' (quick)' if quick else ''}.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
