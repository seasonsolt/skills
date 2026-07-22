#!/usr/bin/env python3
"""Validate sticky production-fix policy across campaign artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


POLICY_INVALID = 2
ALLOWED_POLICIES = {"record-only-confirmed", "authorized-ticket-scoped"}
# 票据 ID 统一文法（与 batch_run.py / generate_triage.py 保持一致）：
# 纯数字遗留 ID，或 `<领域>-<批次>-<序号>` 形式的字母数字域 + 至少一个数字段。
TICKET_ID_GRAMMAR = r"\d+|[A-Za-z][A-Za-z0-9]*(?:-\d+)+"
ALLOWED_CAMPAIGN_STATUSES = {"draft", "in-progress", "complete", "residual-accepted"}
ALLOWED_FINDING_TYPES = {"defect", "suspected", "test-hygiene"}
ALLOWED_VERIFICATIONS = {"confirmed", "suspected", "latent", "test-hygiene"}
ALLOWED_SEVERITIES = {"high", "medium", "low"}
TEST_REFERENCE = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*"
    r"#[A-Za-z_$][A-Za-z0-9_$]*$"
)
FORWARD_AUTHORIZATION_PATTERNS = (
    re.compile(r"awaiting\s+production[- ]fix\s+authorization", re.IGNORECASE),
    re.compile(
        r"decide\s+whether\s+to\s+authorize.{0,80}production\s+fix",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"ask.{0,40}(?:for|whether).{0,40}production[- ]fix\s+authorization",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"等待.{0,40}(?:生产代码|生产|业务代码)?.{0,12}修复.{0,20}授权"),
    re.compile(r"决定是否.{0,40}(?:生产代码|生产|业务代码)?.{0,12}修复"),
    re.compile(r"是否.{0,20}授权.{0,30}(?:生产代码|生产|业务代码)?.{0,12}修复"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate production-fix policy consistency in a test campaign."
    )
    parser.add_argument(
        "--campaign-dir", required=True, type=Path, help="Campaign working directory"
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format"
    )
    return parser.parse_args()


def read_required(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Missing required artifact: {path.name}")
    return path.read_text(encoding="utf-8")


def machine_value(content: str, key: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*(?:[-*+]\s+)?{re.escape(key)}\s*:\s*(.+?)\s*$",
        content,
    )
    if not match:
        return None
    # 模板允许机器键行尾携带 `<!-- … -->` / ` # …` 枚举说明注释，解析时剥除。
    value = match.group(1).split("<!--", 1)[0]
    value = re.split(r"\s#", value, maxsplit=1)[0]
    value = value.strip().strip("`").strip()
    return value or None


def plan_policy(content: str) -> str | None:
    value = machine_value(content, "production-fix-policy-snapshot")
    if value:
        return value
    match = re.search(
        r"(?im)^\s*Production-fix policy snapshot\s*:\s*`?([^`\s]+)`?\s*$",
        content,
    )
    return match.group(1).strip() if match else None


def artifact_files(campaign: Path) -> list[Path]:
    files = [campaign / "PLAN.md", campaign / "REPORT.md"]
    issues = campaign / "issues"
    if issues.is_dir():
        files.extend(sorted(path for path in issues.glob("*.md") if path.is_file()))
    return files


def issue_files(campaign: Path) -> list[Path]:
    issues = campaign / "issues"
    if not issues.is_dir():
        return []
    return sorted(path for path in issues.glob("*.md") if path.is_file())


def ticket_test_references(content: str, key: str) -> list[str] | None:
    match = re.search(
        rf"(?im)^\s*{re.escape(key)}\s*:\s*(.*?)\s*$",
        content,
    )
    if not match:
        return None
    return re.findall(r"`([^`]+)`", match.group(1))


def expected_priority(verification: str | None, severity: str | None) -> str | None:
    if verification == "confirmed" and severity == "high":
        return "P0"
    if verification == "confirmed" and severity == "medium":
        return "P1"
    if verification in ALLOWED_VERIFICATIONS and severity in ALLOWED_SEVERITIES:
        return "P2"
    return None


def validate_ticket_evidence(campaign: Path) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for path in issue_files(campaign):
        content = read_required(path)
        relative_path = relative(campaign, path)
        finding_type = machine_value(content, "finding-type")
        verification = machine_value(content, "verification")
        severity = machine_value(content, "severity")
        priority = machine_value(content, "priority")
        characterization = ticket_test_references(content, "characterization-tests")
        regression = ticket_test_references(content, "regression-tests")

        for value, allowed, missing_kind, invalid_kind in (
            (finding_type, ALLOWED_FINDING_TYPES, "missing-finding-type", "invalid-finding-type"),
            (verification, ALLOWED_VERIFICATIONS, "missing-verification", "invalid-verification"),
            (severity, ALLOWED_SEVERITIES, "missing-severity", "invalid-severity"),
        ):
            if value is None:
                violations.append({"path": relative_path, "kind": missing_kind})
            elif value not in allowed:
                violations.append(
                    {"path": relative_path, "kind": invalid_kind, "detail": value}
                )

        derived_priority = expected_priority(verification, severity)
        if priority is None:
            violations.append({"path": relative_path, "kind": "missing-priority"})
        elif derived_priority is not None and priority != derived_priority:
            violations.append(
                {
                    "path": relative_path,
                    "kind": "priority-mismatch",
                    "detail": f"expected={derived_priority}, actual={priority}",
                }
            )

        requires_characterization = finding_type in {"defect", "suspected"}
        requires_regression = False
        for key, references, required in (
            ("characterization", characterization, requires_characterization),
            ("regression", regression, requires_regression),
        ):
            if references is None:
                if required:
                    violations.append(
                        {"path": relative_path, "kind": f"missing-{key}-tests"}
                    )
                continue
            if required and not references:
                violations.append(
                    {"path": relative_path, "kind": f"missing-{key}-tests"}
                )
                continue
            for reference in references:
                if not TEST_REFERENCE.fullmatch(reference):
                    violations.append(
                        {
                            "path": relative_path,
                            "kind": f"invalid-{key}-test-reference",
                            "detail": reference,
                        }
                    )
    return violations


def relative(campaign: Path, path: Path) -> str:
    return path.relative_to(campaign).as_posix()


def validate(campaign: Path) -> tuple[dict[str, Any], int]:
    if not campaign.is_dir():
        return {"result": "POLICY_INVALID", "message": "Campaign directory is missing."}, POLICY_INVALID

    try:
        prd = read_required(campaign / "PRD.md")
        plan = read_required(campaign / "PLAN.md")
        report = read_required(campaign / "REPORT.md")
    except (OSError, UnicodeError, ValueError) as exc:
        return {"result": "POLICY_INVALID", "message": str(exc)}, POLICY_INVALID

    campaign_status = machine_value(prd, "campaign-status")
    ticket_evidence_version = machine_value(prd, "ticket-evidence-version")
    if campaign_status not in ALLOWED_CAMPAIGN_STATUSES:
        return {
            "result": "POLICY_INVALID",
            "message": "PRD.md has no valid campaign-status.",
        }, POLICY_INVALID
    if ticket_evidence_version not in {None, "1"}:
        return {
            "result": "POLICY_INVALID",
            "message": "PRD.md has an unsupported ticket-evidence-version.",
            "ticket_evidence_version": ticket_evidence_version,
        }, POLICY_INVALID
    policy = machine_value(prd, "production-fix-policy")
    authorized = machine_value(prd, "authorized-fix-tickets")
    if policy not in ALLOWED_POLICIES:
        return {
            "result": "POLICY_INVALID",
            "message": "PRD.md has no valid production-fix-policy.",
            "production_fix_policy": policy,
        }, POLICY_INVALID
    if not authorized:
        return {
            "result": "POLICY_INVALID",
            "message": "PRD.md has no authorized-fix-tickets value.",
            "production_fix_policy": policy,
        }, POLICY_INVALID
    if policy == "record-only-confirmed" and authorized != "none":
        return {
            "result": "POLICY_INVALID",
            "message": "record-only-confirmed requires authorized-fix-tickets: none.",
            "production_fix_policy": policy,
        }, POLICY_INVALID
    if policy == "authorized-ticket-scoped" and not re.fullmatch(
        rf"issues/(?:{TICKET_ID_GRAMMAR})(?:\s*,\s*issues/(?:{TICKET_ID_GRAMMAR}))*",
        authorized,
    ):
        return {
            "result": "POLICY_INVALID",
            "message": "authorized-ticket-scoped requires an explicit issues/<ticket-id> list.",
            "production_fix_policy": policy,
        }, POLICY_INVALID

    snapshot = plan_policy(plan)
    if snapshot != policy:
        return {
            "result": "POLICY_CONTRADICTION",
            "message": "PLAN.md policy snapshot does not match PRD.md.",
            "production_fix_policy": policy,
            "violations": [{"path": "PLAN.md", "kind": "policy-snapshot-mismatch"}],
        }, POLICY_INVALID

    violations: list[dict[str, str]] = []
    if policy == "record-only-confirmed":
        for path in artifact_files(campaign):
            try:
                content = read_required(path)
            except (OSError, UnicodeError, ValueError) as exc:
                violations.append(
                    {"path": relative(campaign, path), "kind": "unreadable", "detail": str(exc)}
                )
                continue
            for pattern in FORWARD_AUTHORIZATION_PATTERNS:
                match = pattern.search(content)
                if match:
                    violations.append(
                        {
                            "path": relative(campaign, path),
                            "kind": "reopened-production-fix-authorization",
                            "detail": " ".join(match.group(0).split())[:160],
                        }
                    )
                    break

    if violations:
        return {
            "result": "POLICY_CONTRADICTION",
            "message": "Campaign artifacts contradict the sticky production-fix policy.",
            "production_fix_policy": policy,
            "violations": violations,
        }, POLICY_INVALID

    ticket_violations = (
        validate_ticket_evidence(campaign) if ticket_evidence_version == "1" else []
    )
    if ticket_violations:
        return {
            "result": "TICKET_EVIDENCE_INVALID",
            "message": "Local issue tickets do not contain traceable test evidence.",
            "production_fix_policy": policy,
            "violations": ticket_violations,
        }, POLICY_INVALID
    return {
        "result": "VALID",
        "campaign_status": campaign_status,
        "ticket_evidence_version": ticket_evidence_version,
        "production_fix_policy": policy,
        "authorized_fix_tickets": authorized,
        "checked_files": [relative(campaign, path) for path in artifact_files(campaign)],
    }, 0


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(f"Result: {payload['result']}")
    if "message" in payload:
        print(payload["message"])
    for violation in payload.get("violations", []):
        print(f"- {violation['path']}: {violation['kind']}")


def main() -> int:
    args = parse_args()
    payload, exit_code = validate(args.campaign_dir.expanduser().resolve())
    emit(payload, args.format)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
