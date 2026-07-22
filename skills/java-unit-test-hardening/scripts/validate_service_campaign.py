#!/usr/bin/env python3
"""Validate service-wide core-flow inventory and campaign closure."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure the sibling module is importable whether this script is run by direct
# path (its directory is already sys.path[0]) or as `python -m ...` (it is not).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_campaign import validate as validate_workflow_campaign


INVALID = 2
SERVICE_STATUSES = {"in-progress", "complete", "residual-accepted"}
INVENTORY_STATUSES = {"partial", "complete"}
WORKFLOW_STATUSES = {
    "pending",
    "in-progress",
    "complete",
    "refresh-needed",
    "residual-accepted",
}
TERMINAL_WORKFLOW_STATUSES = {"complete", "residual-accepted"}
TERMINAL_SERVICE_STATUSES = {"complete", "residual-accepted"}
YES_NO = {"yes", "no"}
BACKLOG_COLUMNS = {
    "workflow-id",
    "module-id",
    "core",
    "priority",
    "workflow",
    "status",
    "artifact-dir",
}
MODULE_COLUMNS = {
    "module-id",
    "module-path",
    "scan-status",
    "discovered-entry-count",
    "mapped-entry-count",
    "excluded-entry-count",
    "evidence",
}
FLOW_COLUMNS = {
    "flow-id",
    "module-id",
    "entry-symbols",
    "workflow-id",
    "core",
    "evidence",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate service-level test-hardening campaign closure."
    )
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def read_required(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Missing required artifact: {path.name}")
    return path.read_text(encoding="utf-8")


def clean_cell(value: str) -> str:
    return value.strip().strip("`").strip()


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
    value = clean_cell(value)
    return value or None


def parse_tables(content: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    lines = content.splitlines()
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    index = 0
    while index + 1 < len(lines):
        header_line = lines[index].strip()
        separator_line = lines[index + 1].strip()
        if not header_line.startswith("|") or not separator_line.startswith("|"):
            index += 1
            continue
        headers = [clean_cell(cell) for cell in header_line.strip("|").split("|")]
        separators = [clean_cell(cell) for cell in separator_line.strip("|").split("|")]
        if len(headers) != len(separators) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in separators
        ):
            index += 1
            continue
        rows: list[dict[str, str]] = []
        index += 2
        while index < len(lines) and lines[index].strip().startswith("|"):
            cells = [clean_cell(cell) for cell in lines[index].strip().strip("|").split("|")]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells, strict=True)))
            index += 1
        tables.append((headers, rows))
    return tables


def table_with_columns(
    tables: list[tuple[list[str], list[dict[str, str]]]], required: set[str]
) -> list[dict[str, str]] | None:
    for headers, rows in tables:
        if required.issubset(set(headers)):
            return rows
    return None


def parse_nonnegative(value: str) -> int | None:
    return int(value) if value.isdecimal() else None


def violation(path: str, kind: str, detail: str) -> dict[str, str]:
    return {"path": path, "kind": kind, "detail": detail}


def unique_rows(
    rows: list[dict[str, str]], key: str, path: str, violations: list[dict[str, str]]
) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        identifier = row.get(key, "")
        if not identifier:
            violations.append(violation(path, f"missing-{key}", "A row has no identifier."))
        elif identifier in indexed:
            violations.append(violation(path, f"duplicate-{key}", identifier))
        else:
            indexed[identifier] = row
    return indexed


def resolve_artifact_dir(workspace: Path, value: str) -> Path | None:
    if value in {"", "none", "—", "-"}:
        return None
    candidate = Path(value).expanduser()
    resolved = (candidate if candidate.is_absolute() else workspace / candidate).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError:
        return None
    return resolved


def git_head(repository: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    value = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        return None
    return value.lower()


def resolve_repository_root(value: str | None) -> Path | None:
    if not value:
        return None
    repository = Path(value).expanduser().resolve()
    return repository if repository.is_dir() else None


def validate(workspace: Path, campaign: Path) -> tuple[dict[str, Any], int]:
    workspace = workspace.resolve()
    campaign = campaign.resolve()
    try:
        campaign.relative_to(workspace)
    except ValueError:
        return {
            "result": "SERVICE_CAMPAIGN_INVALID",
            "message": "Campaign root must be inside the workspace root.",
        }, INVALID

    try:
        backlog = read_required(campaign / "BACKLOG.md")
        inventory = read_required(campaign / "CORE-FLOW-INVENTORY.md")
    except (OSError, UnicodeError, ValueError) as exc:
        return {"result": "SERVICE_CAMPAIGN_INVALID", "message": str(exc)}, INVALID

    service_status = machine_value(backlog, "service-campaign-status")
    backlog_inventory_status = machine_value(backlog, "core-inventory-status")
    completion_policy = machine_value(backlog, "completion-policy")
    service_baseline = machine_value(backlog, "service-baseline")
    repository_root_value = machine_value(backlog, "repository-root")
    inventory_status = machine_value(inventory, "inventory-status")
    inventory_head = machine_value(inventory, "inventory-head")
    violations: list[dict[str, str]] = []

    if service_status not in SERVICE_STATUSES:
        violations.append(
            violation("BACKLOG.md", "invalid-service-status", str(service_status))
        )
    if backlog_inventory_status not in INVENTORY_STATUSES:
        violations.append(
            violation(
                "BACKLOG.md", "invalid-inventory-status", str(backlog_inventory_status)
            )
        )
    if inventory_status != backlog_inventory_status:
        violations.append(
            violation(
                "CORE-FLOW-INVENTORY.md",
                "inventory-status-mismatch",
                f"backlog={backlog_inventory_status}, inventory={inventory_status}",
            )
        )
    if completion_policy != "all-core-workflows":
        violations.append(
            violation(
                "BACKLOG.md", "invalid-completion-policy", str(completion_policy)
            )
        )
    if not service_baseline or not re.fullmatch(r"[0-9a-fA-F]{40}", service_baseline):
        violations.append(
            violation("BACKLOG.md", "invalid-service-baseline", str(service_baseline))
        )
    if not inventory_head or not re.fullmatch(r"[0-9a-fA-F]{40}", inventory_head):
        violations.append(
            violation(
                "CORE-FLOW-INVENTORY.md", "invalid-inventory-head", str(inventory_head)
            )
        )

    backlog_rows = table_with_columns(parse_tables(backlog), BACKLOG_COLUMNS)
    inventory_tables = parse_tables(inventory)
    module_rows = table_with_columns(inventory_tables, MODULE_COLUMNS)
    flow_rows = table_with_columns(inventory_tables, FLOW_COLUMNS)
    if backlog_rows is None or not backlog_rows:
        violations.append(
            violation("BACKLOG.md", "workflow-table-missing", "No workflow rows found.")
        )
        backlog_rows = []
    if module_rows is None or not module_rows:
        violations.append(
            violation(
                "CORE-FLOW-INVENTORY.md",
                "module-table-missing",
                "No module inventory rows found.",
            )
        )
        module_rows = []
    if flow_rows is None or not flow_rows:
        violations.append(
            violation(
                "CORE-FLOW-INVENTORY.md",
                "flow-table-missing",
                "No flow inventory rows found.",
            )
        )
        flow_rows = []

    workflows = unique_rows(backlog_rows, "workflow-id", "BACKLOG.md", violations)
    modules = unique_rows(
        module_rows, "module-id", "CORE-FLOW-INVENTORY.md", violations
    )
    flows = unique_rows(flow_rows, "flow-id", "CORE-FLOW-INVENTORY.md", violations)

    for workflow_id, row in workflows.items():
        if row["status"] not in WORKFLOW_STATUSES:
            violations.append(
                violation(
                    "BACKLOG.md",
                    "invalid-workflow-status",
                    f"{workflow_id}: {row['status']}",
                )
            )
        if row["core"] not in YES_NO:
            violations.append(
                violation(
                    "BACKLOG.md", "invalid-core-flag", f"{workflow_id}: {row['core']}"
                )
            )
        if row["module-id"] not in modules:
            violations.append(
                violation(
                    "BACKLOG.md",
                    "workflow-module-missing",
                    f"{workflow_id}: {row['module-id']}",
                )
            )

    mapped_core_workflows: set[str] = set()
    for flow_id, row in flows.items():
        if row["core"] not in YES_NO:
            violations.append(
                violation(
                    "CORE-FLOW-INVENTORY.md",
                    "invalid-core-flag",
                    f"{flow_id}: {row['core']}",
                )
            )
        if row["module-id"] not in modules:
            violations.append(
                violation(
                    "CORE-FLOW-INVENTORY.md",
                    "inventory-module-missing",
                    f"{flow_id}: {row['module-id']}",
                )
            )
        mapped = row["workflow-id"]
        if mapped not in workflows:
            violations.append(
                violation(
                    "CORE-FLOW-INVENTORY.md",
                    "inventory-workflow-missing",
                    f"{flow_id}: {mapped}",
                )
            )
        elif row["core"] == "yes":
            mapped_core_workflows.add(mapped)
            if workflows[mapped]["core"] != "yes":
                violations.append(
                    violation(
                        "CORE-FLOW-INVENTORY.md",
                        "core-mapping-mismatch",
                        f"{flow_id} maps to non-core workflow {mapped}",
                    )
                )

    core_workflows = {
        workflow_id: row for workflow_id, row in workflows.items() if row["core"] == "yes"
    }
    for workflow_id in sorted(set(core_workflows) - mapped_core_workflows):
        violations.append(
            violation(
                "BACKLOG.md",
                "core-workflow-without-inventory-flow",
                workflow_id,
            )
        )

    if inventory_status == "complete":
        for module_id, row in modules.items():
            if row["scan-status"] != "complete":
                violations.append(
                    violation(
                        "CORE-FLOW-INVENTORY.md",
                        "module-scan-not-complete",
                        module_id,
                    )
                )
            counts = [
                parse_nonnegative(row["discovered-entry-count"]),
                parse_nonnegative(row["mapped-entry-count"]),
                parse_nonnegative(row["excluded-entry-count"]),
            ]
            if any(count is None for count in counts):
                violations.append(
                    violation(
                        "CORE-FLOW-INVENTORY.md",
                        "invalid-module-entry-count",
                        module_id,
                    )
                )
            elif counts[0] != counts[1] + counts[2]:
                violations.append(
                    violation(
                        "CORE-FLOW-INVENTORY.md",
                        "module-entry-count-mismatch",
                        f"{module_id}: discovered={counts[0]}, mapped={counts[1]}, excluded={counts[2]}",
                    )
                )

    for workflow_id, row in workflows.items():
        if row["status"] not in TERMINAL_WORKFLOW_STATUSES:
            continue
        artifact_dir = resolve_artifact_dir(workspace, row["artifact-dir"])
        if artifact_dir is None:
            violations.append(
                violation(
                    "BACKLOG.md", "terminal-workflow-artifact-missing", workflow_id
                )
            )
            continue
        payload, exit_code = validate_workflow_campaign(artifact_dir)
        if exit_code != 0:
            violations.append(
                violation(
                    row["artifact-dir"],
                    "workflow-campaign-invalid",
                    payload.get("message", payload.get("result", "invalid")),
                )
            )
        elif payload.get("campaign_status") != row["status"]:
            violations.append(
                violation(
                    row["artifact-dir"],
                    "workflow-status-mismatch",
                    f"backlog={row['status']}, artifact={payload.get('campaign_status')}",
                )
            )

    all_core_terminal = bool(core_workflows) and all(
        row["status"] in TERMINAL_WORKFLOW_STATUSES for row in core_workflows.values()
    )
    expected_terminal_status = (
        "residual-accepted"
        if any(row["status"] == "residual-accepted" for row in core_workflows.values())
        else "complete"
    )

    if service_status in TERMINAL_SERVICE_STATUSES:
        repository = resolve_repository_root(repository_root_value)
        if repository is None:
            violations.append(
                violation(
                    "BACKLOG.md",
                    "repository-root-invalid",
                    str(repository_root_value),
                )
            )
        else:
            current_head = git_head(repository)
            if current_head is None:
                violations.append(
                    violation(
                        "BACKLOG.md",
                        "repository-head-unavailable",
                        str(repository),
                    )
                )
            else:
                if inventory_head and inventory_head.lower() != current_head:
                    violations.append(
                        violation(
                            "CORE-FLOW-INVENTORY.md",
                            "inventory-head-stale",
                            f"inventory={inventory_head}, repository={current_head}",
                        )
                    )
        # 服务终态不得携带悬挂的活跃批次指针：active-batch-* 机器键由批次
        # 协调者维护，收口时必须已复位为 none（键缺失视为遗留格式放行）。
        for key in ("active-batch-id", "active-batch-run", "active-batch-status"):
            value = machine_value(backlog, key)
            if value is not None and value != "none":
                violations.append(
                    violation("BACKLOG.md", "active-batch-dangling", f"{key}={value}")
                )
        if not core_workflows:
            violations.append(
                violation(
                    "BACKLOG.md",
                    "no-core-workflows-for-closure",
                    "completion-policy all-core-workflows needs at least one core workflow",
                )
            )
        if inventory_status != "complete":
            violations.append(
                violation(
                    "BACKLOG.md",
                    "inventory-not-complete",
                    f"inventory-status={inventory_status}",
                )
            )
        for workflow_id, row in core_workflows.items():
            if row["status"] not in TERMINAL_WORKFLOW_STATUSES:
                violations.append(
                    violation(
                        "BACKLOG.md",
                        "core-workflow-not-terminal",
                        f"{workflow_id}: {row['status']}",
                    )
                )
        if all_core_terminal and service_status != expected_terminal_status:
            violations.append(
                violation(
                    "BACKLOG.md",
                    "service-status-mismatch",
                    f"expected={expected_terminal_status}, actual={service_status}",
                )
            )
        try:
            report = read_required(campaign / "SERVICE-REPORT.md")
        except (OSError, UnicodeError, ValueError) as exc:
            violations.append(
                violation("SERVICE-REPORT.md", "service-report-missing", str(exc))
            )
        else:
            report_status = machine_value(report, "service-campaign-status")
            expected_counts = {
                "core-workflows-total": len(core_workflows),
                "core-workflows-complete": sum(
                    row["status"] == "complete" for row in core_workflows.values()
                ),
                "core-workflows-residual-accepted": sum(
                    row["status"] == "residual-accepted"
                    for row in core_workflows.values()
                ),
            }
            if report_status != service_status:
                violations.append(
                    violation(
                        "SERVICE-REPORT.md",
                        "service-report-status-mismatch",
                        f"backlog={service_status}, report={report_status}",
                    )
                )
            for key, expected in expected_counts.items():
                actual = machine_value(report, key)
                if actual is None or not actual.isdecimal() or int(actual) != expected:
                    violations.append(
                        violation(
                            "SERVICE-REPORT.md",
                            "service-report-count-mismatch",
                            f"{key}: expected={expected}, actual={actual}",
                        )
                    )

    if violations:
        return {
            "result": "SERVICE_CAMPAIGN_INVALID",
            "message": "Service campaign artifacts do not satisfy the core-flow contract.",
            "service_campaign_status": service_status,
            "closure_ready": False,
            "violations": violations,
        }, INVALID

    closure_ready = (
        service_status in TERMINAL_SERVICE_STATUSES
        and inventory_status == "complete"
        and all_core_terminal
    )
    return {
        "result": "VALID",
        "service_campaign_status": service_status,
        "core_inventory_status": inventory_status,
        "core_workflows_total": len(core_workflows),
        "core_workflows_terminal": sum(
            row["status"] in TERMINAL_WORKFLOW_STATUSES
            for row in core_workflows.values()
        ),
        "closure_ready": closure_ready,
    }, 0


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(f"Result: {payload['result']}")
    if "message" in payload:
        print(payload["message"])
    for item in payload.get("violations", []):
        print(f"- {item['path']}: {item['kind']} ({item['detail']})")


def main() -> int:
    args = parse_args()
    payload, exit_code = validate(
        args.workspace_root.expanduser(), args.campaign_root.expanduser()
    )
    emit(payload, args.format)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
