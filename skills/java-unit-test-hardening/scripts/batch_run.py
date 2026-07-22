#!/usr/bin/env python3
"""Seal, audit, and atomically advance one approved test-hardening batch."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import preflight as target_preflight
from validate_campaign import (
    TICKET_ID_GRAMMAR,
    machine_value,
    ticket_test_references,
    validate as validate_campaign,
)


INVALID = 2
TERMINAL_WORKFLOW_STATUSES = {"complete", "residual-accepted"}
SOURCE_WORKFLOW_STATUSES = {"pending", "refresh-needed", "in-progress"}
BATCH_STATUSES = {
    "confirmed",
    "running",
    "paused",
    "needs-reconfirm",
    "complete",
}
INTEGRATION_LANES = {"required", "not-applicable"}


def add_mutation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-file", required=True, type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--at", required=True)
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument("--format", choices=("text", "json"), default="text")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seal, audit, or atomically advance a confirmed test-hardening batch."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("seal", "validate"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--run-file", required=True, type=Path)
        subparser.add_argument("--format", choices=("text", "json"), default="text")

    audit = subparsers.add_parser("audit")
    add_mutation_arguments(audit)
    audit.add_argument("--workflow", required=True)

    for command in ("advance", "transition"):
        transition = subparsers.add_parser(command)
        add_mutation_arguments(transition)
        transition.add_argument("--workflow", required=True)
        transition.add_argument(
            "--to",
            required=True,
            choices=("in-progress", "complete", "residual-accepted"),
        )
        transition.add_argument("--evidence")
        transition.add_argument("--evidence-manifest", type=Path)

    pause = subparsers.add_parser("pause")
    add_mutation_arguments(pause)
    pause.add_argument("--reason", required=True)
    pause.add_argument("--resume-command", required=True)

    resume = subparsers.add_parser("resume")
    add_mutation_arguments(resume)

    residual = subparsers.add_parser("accept-residual")
    add_mutation_arguments(residual)
    residual.add_argument("--workflow", required=True)
    residual.add_argument("--evidence-manifest", required=True, type=Path)
    residual.add_argument("--acceptance-file", required=True, type=Path)

    transfer = subparsers.add_parser("transfer-writer")
    add_mutation_arguments(transfer)
    transfer.add_argument("--new-writer", required=True)
    transfer.add_argument("--reason", required=True)
    transfer.add_argument("--workflow")

    invalidate = subparsers.add_parser("invalidate")
    add_mutation_arguments(invalidate)
    invalidate.add_argument("--reason", required=True)
    invalidate.add_argument("--evidence", required=True)
    return parser.parse_args()


def violation(kind: str, detail: str) -> dict[str, str]:
    return {"kind": kind, "detail": detail}


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_timestamp(value: Any) -> datetime | None:
    if not nonempty_string(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolved_path(raw_path: Any, base: Path) -> Path | None:
    if not nonempty_string(raw_path):
        return None
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        return candidate.resolve(strict=True)
    except OSError:
        return None


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def read_json_file(path: Path, *, maximum_size: int = 2 * 1024 * 1024) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_size:
        raise ValueError(f"JSON file is missing, symlinked, or too large: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def read_payload(run_file: Path) -> dict[str, Any]:
    return read_json_file(run_file)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        # Persist the rename itself: without a parent-directory fsync, a crash
        # after os.replace can drop the just-committed journal transition,
        # because the journal is a whole-file rewrite, not a separate WAL.
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def run_lock(run_file: Path, *, exclusive: bool) -> Iterator[None]:
    lock_file = run_file.with_name(f".{run_file.name}.lock")
    with lock_file.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def expected_campaign_root(payload: dict[str, Any], workspace: Path) -> Path:
    return workspace / ".scratch" / f"{payload['service']}-test-campaign"


def is_parallel(payload: dict[str, Any]) -> bool:
    return payload.get("execution_mode") == "parallel"


def effective_max_concurrent(payload: dict[str, Any]) -> int:
    value = payload.get("max_concurrent_workflows")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return 1


def workflow_worktree_path(
    payload: dict[str, Any], workflow: dict[str, Any] | None
) -> Path | None:
    """Resolve a workflow's immutable worktree binding under the workspace root.

    Returns None for sequential workflows (no worktree bound); the path is not
    required to exist here — existence is a live boundary-audit fact.
    """
    raw = workflow.get("worktree") if isinstance(workflow, dict) else None
    if not nonempty_string(raw):
        return None
    return (Path(payload["workspace_root"]).resolve() / str(raw)).resolve()


def validate_workflow_contracts(
    payload: dict[str, Any], workspace: Path, repository: Path
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    violations: list[dict[str, str]] = []
    workflows = payload.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        return [violation("invalid-workflows", "At least one workflow is required.")], {}
    by_id: dict[str, dict[str, Any]] = {}
    orders: set[int] = set()
    parallel = is_parallel(payload)
    worktrees_seen: set[str] = set()
    for workflow in workflows:
        if not isinstance(workflow, dict):
            violations.append(violation("invalid-workflow", str(workflow)))
            continue
        workflow_id = workflow.get("workflow_id")
        if not nonempty_string(workflow_id) or workflow_id in by_id:
            violations.append(violation("duplicate-or-invalid-workflow", str(workflow_id)))
            continue
        by_id[workflow_id] = workflow
        order = workflow.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1 or order in orders:
            violations.append(violation("duplicate-or-invalid-order", f"{workflow_id}: {order}"))
        else:
            orders.add(order)
        if not nonempty_string(workflow.get("module_id")):
            violations.append(violation("invalid-module-id", workflow_id))
        dependencies = workflow.get("dependencies")
        if not isinstance(dependencies, list) or any(
            not nonempty_string(dependency) for dependency in dependencies
        ):
            violations.append(violation("invalid-dependencies", workflow_id))
        if workflow.get("source_status") not in SOURCE_WORKFLOW_STATUSES:
            violations.append(violation("invalid-source-status", workflow_id))
        artifact_raw = workflow.get("artifact_dir")
        if not nonempty_string(artifact_raw):
            # 缺失/空串会让 fallback 解析成 workspace 自身而恒通过，
            # 且延迟到 terminal transition 时才以 KeyError 崩溃——在契约层直接拒绝。
            violations.append(violation("invalid-artifact-dir", workflow_id))
        else:
            artifact = resolved_path(artifact_raw, workspace)
            if artifact is None:
                candidate = Path(str(artifact_raw))
                if not candidate.is_absolute():
                    candidate = workspace / candidate
                try:
                    candidate.resolve().relative_to(workspace)
                except ValueError:
                    violations.append(violation("invalid-artifact-dir", workflow_id))
            elif not is_within(artifact, workspace):
                violations.append(violation("invalid-artifact-dir", workflow_id))
        docs_path = workflow.get("docs_path")
        if not nonempty_string(docs_path):
            violations.append(violation("invalid-docs-path", workflow_id))
        else:
            docs_candidate = Path(docs_path)
            if (
                docs_candidate.is_absolute()
                or ".." in docs_candidate.parts
                or docs_candidate.parts[:2] != ("docs", "tests")
            ):
                violations.append(violation("invalid-docs-path", workflow_id))
        test_build_files = workflow.get("test_build_files")
        if not isinstance(test_build_files, list) or any(
            not nonempty_string(path)
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or not (path == "pom.xml" or path.endswith("/pom.xml"))
            for path in test_build_files
        ):
            violations.append(violation("invalid-test-build-files", workflow_id))
        lane = workflow.get("integration_lane")
        if lane not in INTEGRATION_LANES:
            violations.append(violation("invalid-integration-lane", workflow_id))
        worktree = workflow.get("worktree")
        branch = workflow.get("branch")
        writer = workflow.get("writer")
        if parallel:
            # parallel mode binds every workflow immutably to its own linked
            # worktree, branch, and writer; worktrees must stay distinct and
            # inside the workspace (workspace-relative, no escapes).
            if (
                not nonempty_string(worktree)
                or Path(str(worktree)).is_absolute()
                or ".." in Path(str(worktree)).parts
            ):
                violations.append(violation("invalid-workflow-worktree", workflow_id))
            elif str(Path(str(worktree))) in worktrees_seen:
                violations.append(violation("duplicate-worktree", workflow_id))
            else:
                worktrees_seen.add(str(Path(str(worktree))))
            if not nonempty_string(branch):
                violations.append(violation("invalid-workflow-branch", workflow_id))
            if not nonempty_string(writer):
                violations.append(violation("invalid-workflow-writer", workflow_id))
        else:
            for key, value in (
                ("worktree", worktree),
                ("branch", branch),
                ("writer", writer),
            ):
                if value is not None:
                    violations.append(
                        violation(
                            f"invalid-workflow-{key}",
                            f"{workflow_id}: must be null in sequential mode",
                        )
                    )
    if orders and orders != set(range(1, len(workflows) + 1)):
        violations.append(violation("non-contiguous-order", str(sorted(orders))))
    in_progress_sources = [
        workflow
        for workflow in by_id.values()
        if workflow.get("source_status") == "in-progress"
    ]
    if len(in_progress_sources) > 1 or (
        in_progress_sources and in_progress_sources[0].get("order") != 1
    ):
        violations.append(
            violation(
                "invalid-resume-source-order",
                ",".join(workflow["workflow_id"] for workflow in in_progress_sources),
            )
        )
    for workflow_id, workflow in by_id.items():
        for dependency in workflow.get("dependencies", []):
            candidate = by_id.get(dependency)
            if candidate is None:
                violations.append(violation("dependency-not-selected", f"{workflow_id}: {dependency}"))
            elif candidate.get("order", 0) >= workflow.get("order", 0):
                violations.append(violation("dependency-order-invalid", f"{workflow_id}: {dependency}"))
    return violations, by_id


def base_validation(
    payload: Any, run_file: Path, *, allow_unsealed: bool
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    if not isinstance(payload, dict):
        return [violation("invalid-root", "BATCH-RUN root must be an object.")], {}
    violations: list[dict[str, str]] = []
    if payload.get("version") != 2:
        violations.append(violation("invalid-version", str(payload.get("version"))))
    for key in (
        "batch_id",
        "service",
        "workspace_root",
        "repository_root",
        "branch",
    ):
        if not nonempty_string(payload.get(key)):
            violations.append(violation(f"invalid-{key.replace('_', '-')}", str(payload.get(key))))
    workspace = resolved_path(payload.get("workspace_root"), run_file.parent)
    repository = resolved_path(payload.get("repository_root"), run_file.parent)
    if workspace is None or not workspace.is_dir():
        violations.append(violation("workspace-missing", str(payload.get("workspace_root"))))
        workspace = run_file.parent
    if repository is None or not repository.is_dir():
        violations.append(violation("repository-missing", str(payload.get("repository_root"))))
        repository = run_file.parent
    if workspace and nonempty_string(payload.get("service")):
        expected_root = expected_campaign_root(payload, workspace)
        try:
            run_file.relative_to(expected_root / "batches" / str(payload.get("batch_id")))
        except ValueError:
            violations.append(
                violation("invalid-run-file-location", str(run_file))
            )
    baseline = payload.get("baseline")
    if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", baseline):
        violations.append(violation("invalid-baseline", str(baseline)))
    inventory = resolved_path(payload.get("inventory_path"), run_file.parent)
    inventory_hash = payload.get("inventory_sha256")
    if inventory is None or not inventory.is_file():
        violations.append(violation("inventory-missing", str(payload.get("inventory_path"))))
    elif not isinstance(inventory_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", inventory_hash):
        violations.append(violation("invalid-inventory-hash", str(inventory_hash)))
    elif file_sha256(inventory) != inventory_hash:
        violations.append(violation("inventory-drift", str(inventory)))
    if payload.get("production_fix_policy") not in {
        "record-only-confirmed",
        "authorized-ticket-scoped",
    }:
        violations.append(violation("invalid-production-fix-policy", str(payload.get("production_fix_policy"))))
    execution_mode = payload.get("execution_mode")
    if execution_mode not in {"sequential", "parallel"}:
        violations.append(violation("invalid-execution-mode", str(execution_mode)))
    max_concurrent = payload.get("max_concurrent_workflows")
    if execution_mode == "parallel":
        if (
            not isinstance(max_concurrent, int)
            or isinstance(max_concurrent, bool)
            or not 1 <= max_concurrent <= 8
        ):
            violations.append(
                violation("invalid-max-concurrent-workflows", str(max_concurrent))
            )
    elif max_concurrent not in (None, 1):
        violations.append(
            violation("invalid-max-concurrent-workflows", str(max_concurrent))
        )
    selection = payload.get("selection")
    if not isinstance(selection, dict):
        violations.append(violation("invalid-selection", "selection must be an object."))
    else:
        if not nonempty_string(selection.get("approved_by")):
            violations.append(violation("invalid-approved-by", str(selection.get("approved_by"))))
        if parse_timestamp(selection.get("approved_at")) is None:
            violations.append(violation("invalid-approved-at", str(selection.get("approved_at"))))
        if not nonempty_string(selection.get("decision_source")):
            violations.append(violation("invalid-decision-source", str(selection.get("decision_source"))))
    agent_policy = payload.get("agent_policy")
    if not isinstance(agent_policy, dict) or (
        not nonempty_string(agent_policy.get("coordinator"))
        or not nonempty_string(agent_policy.get("initial_writer"))
        or not isinstance(agent_policy.get("read_only_subagents"), bool)
    ):
        violations.append(violation("invalid-writer-policy", str(agent_policy)))
    workflow_violations, workflows = validate_workflow_contracts(
        payload, workspace, repository
    )
    violations.extend(workflow_violations)
    if allow_unsealed:
        if payload.get("repository_baseline") is not None:
            violations.append(violation("unsealed-repository-baseline", "repository_baseline must be null before seal."))
        if payload.get("transitions") != []:
            violations.append(violation("invalid-initial-journal", "Unsealed batch must have no events."))
    else:
        if not isinstance(payload.get("repository_baseline"), dict):
            violations.append(
                violation(
                    "repository-baseline-missing",
                    str(payload.get("repository_baseline")),
                )
            )
    return violations, workflows


def git_root(repository: Path) -> Path:
    return Path(target_preflight.git(repository, "rev-parse", "--show-toplevel")).resolve()


def validate_repository_modules(repository: Path) -> list[str]:
    modules = target_preflight.maven_modules(repository / "pom.xml")
    for module in modules:
        target_preflight.validate_maven_module_root(
            repository,
            module,
            invalid_result="MAVEN_INVALID",
            exit_code=target_preflight.HARD_BLOCK,
        )
    return modules


def bulk_path_facts(repository: Path, paths: list[str]) -> dict[str, dict[str, Any]]:
    """批量版 path_facts：整仓两个 git 进程拿全部状态/OID，再逐文件哈希。
    审计路径数随 campaign 单调增长，逐路径起 git 进程会线性放大为子进程风暴。"""
    git_facts = target_preflight.bulk_git_path_index_facts(repository, paths)
    facts: dict[str, dict[str, Any]] = {}
    for path in paths:
        state, digest = target_preflight.path_content_digest(repository, path)
        git_status, index_oid = git_facts[path]
        facts[path] = {
            "path": path,
            "state": state,
            "sha256": digest,
            "git_status": git_status,
            "index_oid": index_oid,
        }
    return facts


def verify_worktree(
    payload: dict[str, Any],
    workflow: dict[str, Any],
    repository: Path,
    worktree: Path,
) -> list[dict[str, str]]:
    """Verify a parallel workflow's bound path is a live linked worktree of the
    batch repository, on the bound branch, at the batch baseline."""
    workflow_id = workflow["workflow_id"]
    if not worktree.is_dir():
        return [violation("worktree-missing", f"{workflow_id}: {worktree}")]
    try:
        common_raw = target_preflight.git(worktree, "rev-parse", "--git-common-dir")
    except target_preflight.PreflightError:
        return [violation("worktree-not-of-repository", f"{workflow_id}: {worktree}")]
    common_dir = Path(common_raw)
    if not common_dir.is_absolute():
        common_dir = worktree / common_dir
    if common_dir.resolve() != (repository / ".git").resolve():
        return [violation("worktree-not-of-repository", f"{workflow_id}: {common_dir}")]
    violations: list[dict[str, str]] = []
    branch = target_preflight.git(worktree, "branch", "--show-current")
    if branch != workflow["branch"]:
        violations.append(
            violation(
                "worktree-branch-drift",
                f"{workflow_id}: expected={workflow['branch']}, actual={branch}",
            )
        )
    head = target_preflight.git(worktree, "rev-parse", "HEAD")
    if head != payload["baseline"]:
        violations.append(
            violation(
                "worktree-head-drift",
                f"{workflow_id}: expected={payload['baseline']}, actual={head}",
            )
        )
    return violations


def validate_live_identity(
    payload: dict[str, Any], workflow: dict[str, Any] | None = None
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    violations: list[dict[str, str]] = []
    repository = Path(payload["repository_root"]).resolve()
    worktree = workflow_worktree_path(payload, workflow)
    audit_root = worktree if worktree is not None else repository
    branch = head = ""
    tracked: list[str] = []
    modules: list[str] = []
    try:
        if git_root(repository) != repository:
            violations.append(violation("repository-identity-drift", str(repository)))
        worktree_violations: list[dict[str, str]] = []
        if worktree is not None:
            # The worktree branch/HEAD checks replace the main-repository
            # branch/head drift checks: while parallel worktrees run, the main
            # worktree may legitimately sit on another branch. Repository
            # identity above is still verified against repository_root.
            worktree_violations = verify_worktree(payload, workflow, repository, worktree)
            violations.extend(worktree_violations)
        if not worktree_violations:
            branch = target_preflight.git(audit_root, "branch", "--show-current")
            head = target_preflight.git(audit_root, "rev-parse", "HEAD")
            if worktree is None:
                if branch != payload["branch"]:
                    violations.append(violation("branch-drift", f"expected={payload['branch']}, actual={branch}"))
                if head != payload["baseline"]:
                    violations.append(violation("head-drift", f"expected={payload['baseline']}, actual={head}"))
            tracked, conflicts = target_preflight.tracked_state(audit_root)
            if conflicts:
                violations.append(violation("git-conflict", ",".join(conflicts)))
            operations = target_preflight.git_operation_markers(audit_root)
            if operations:
                violations.append(violation("git-operation-in-progress", ",".join(operations)))
            modules = validate_repository_modules(audit_root)
    except target_preflight.PreflightError as exc:
        violations.append(violation("repository-inspection-failed", f"{exc.result}: {exc.message}"))
        branch, head, tracked, modules = "", "", [], []
    return violations, {
        "repository_root": str(repository),
        "audit_root": str(audit_root),
        "branch": branch,
        "head": head,
        "tracked": tracked,
        "modules": modules,
    }


def capture_repository_baseline(
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    violations, identity = validate_live_identity(payload)
    if violations:
        return None, violations
    repository = Path(payload["repository_root"]).resolve()
    untracked = target_preflight.untracked_files(repository)
    if identity["tracked"] or untracked:
        return None, [
            violation(
                "worktree-not-clean",
                ",".join(sorted(set(identity["tracked"] + untracked))),
            )
        ]
    return {
        "repository_root": str(repository),
        "branch": identity["branch"],
        "head": identity["head"],
        "modules": identity["modules"],
    }, []


def allowed_campaign_path(
    payload: dict[str, Any], path: str, workflow: dict[str, Any] | None = None
) -> bool:
    # TRIAGE.md is regenerated after every workflow and is explicitly a core
    # campaign artifact, independent of any one workflow's docs directory.
    if path == "docs/tests/TRIAGE.md":
        return True
    # workflow=None uses the whole-batch union (the main-repository audit's
    # entry-freeze/drift semantics need it); a bound workflow narrows every
    # scope below to that workflow's own contract, so a parallel writer cannot
    # touch a concurrent workflow's module tree, docs path, or build files
    # inside its own worktree.
    scoped_workflows = [workflow] if workflow is not None else payload["workflows"]
    parts = Path(path).parts
    # A src/test tree is only campaign-owned when it belongs to a module a
    # selected workflow actually targets; module_id is the Maven module path
    # ("root" for the aggregator root). This stops an unrelated module's test
    # tree from silently passing the boundary audit.
    selected_modules = {item["module_id"] for item in scoped_workflows}
    # A workflow may span multiple leaf Maven modules while retaining one
    # campaign-level module_id (for example an aggregator with api and mq
    # children). The sealed test_build_files list is already an explicit,
    # reviewable boundary, so each listed child POM also identifies an allowed
    # src/test root. This keeps unrelated modules prohibited without rejecting
    # tests that belong to a declared multi-module workflow.
    selected_modules.update(
        str(Path(build_file).parent)
        for item in scoped_workflows
        for build_file in item["test_build_files"]
        if Path(build_file).name == "pom.xml" and Path(build_file).parent != Path(".")
    )
    for index in range(max(0, len(parts) - 1)):
        if parts[index : index + 2] != ("src", "test"):
            continue
        module_id = "/".join(parts[:index]) if index else "root"
        if module_id in selected_modules:
            return True
    docs_prefixes = [tuple(Path(item["docs_path"]).parts) for item in scoped_workflows]
    if any(parts[: len(prefix)] == prefix for prefix in docs_prefixes):
        return True
    test_build_files = {
        build_file
        for item in scoped_workflows
        for build_file in item["test_build_files"]
    }
    return path in test_build_files


def boundary_audit(
    payload: dict[str, Any], workflow_id: str
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    workflow = next(
        (item for item in payload["workflows"] if item["workflow_id"] == workflow_id),
        None,
    )
    worktree = workflow_worktree_path(payload, workflow)
    violations, identity = validate_live_identity(payload, workflow=workflow)
    if workflow is None:
        violations.append(violation("workflow-not-selected", workflow_id))
    elif workflow["module_id"] != "root" and workflow["module_id"] not in identity["modules"]:
        violations.append(violation("workflow-module-drift", workflow["module_id"]))
    if worktree is not None:
        # A broken worktree identity means the audit root itself is untrusted;
        # do not inspect paths inside it.
        if violations:
            return None, violations
        untracked = target_preflight.untracked_files(worktree)
        current_paths = sorted(set(identity["tracked"] + untracked))
        audit_facts = bulk_path_facts(worktree, current_paths)
        # A fresh linked worktree at the batch baseline contains none of the
        # main worktree's changes, so every changed path
        # must be owned by THIS workflow's contract, not merely by the batch —
        # writer isolation is what makes parallel execution safe.
        for path in current_paths:
            if not allowed_campaign_path(payload, path, workflow=workflow):
                violations.append(violation("prohibited-repository-path", path))
    else:
        repository = Path(payload["repository_root"]).resolve()
        untracked = target_preflight.untracked_files(repository)
        current_paths = sorted(set(identity["tracked"] + untracked))
        audit_facts = bulk_path_facts(repository, current_paths)
        for path in current_paths:
            if not allowed_campaign_path(payload, path):
                violations.append(violation("prohibited-repository-path", path))
    if violations:
        return None, violations
    changed_facts = [audit_facts[path] for path in current_paths]
    facts = {
        "workflow_id": workflow_id,
        "repository_root": identity["repository_root"],
        "branch": identity["branch"],
        "head": identity["head"],
        "modules": identity["modules"],
        "inventory_sha256": payload["inventory_sha256"],
        "changed_paths": changed_facts,
    }
    if worktree is not None:
        # Bind the audited worktree into the fingerprint; sequential audits
        # keep their exact pre-parallel fact shape.
        facts["worktree"] = workflow["worktree"]
    return {**facts, "fingerprint": canonical_hash(facts)}, []


def initial_derived_state(payload: dict[str, Any]) -> dict[str, Any]:
    initial_writer = payload["agent_policy"]["initial_writer"]
    return {
        "status": "confirmed",
        # current_workflow_ids is ordered by start; current_workflow_id is the
        # backward-compatible mirror: the single element when one workflow is
        # in progress, None when idle, and the MOST RECENTLY STARTED workflow
        # when several run in parallel.
        "current_workflow_id": None,
        "current_workflow_ids": [],
        "pause": None,
        "writer": initial_writer,
        "workflow_writers": {
            workflow["workflow_id"]: workflow.get("writer") or initial_writer
            for workflow in payload["workflows"]
        },
        "workflow_statuses": {
            workflow["workflow_id"]: {"status": "pending", "evidence": None}
            for workflow in payload["workflows"]
        },
        "last_boundary_audit": None,
        "last_boundary_audits": {},
        "revision": 0,
    }


def most_recent_audit(state: dict[str, Any]) -> dict[str, Any] | None:
    """Most recent surviving per-workflow audit (parallel mode)."""
    best_id, best = None, None
    for workflow_id, audit in state["last_boundary_audits"].items():
        if best is None or audit["revision"] > best["revision"]:
            best_id, best = workflow_id, audit
    if best is None:
        return None
    return {"workflow_id": best_id, **best}


def recorded_audit(
    state: dict[str, Any], workflow_id: str, *, parallel: bool
) -> dict[str, Any] | None:
    """The journal-recorded boundary audit a transition for workflow_id may consume."""
    if parallel:
        return state["last_boundary_audits"].get(workflow_id)
    audit = state.get("last_boundary_audit")
    if audit is None or audit.get("workflow_id") != workflow_id:
        return None
    return audit


def bound_audit_fingerprint(
    payload: dict[str, Any], state: dict[str, Any], workflow_id: str
) -> str | None:
    audit = recorded_audit(state, workflow_id, parallel=is_parallel(payload))
    return audit["fingerprint"] if audit is not None else None


def parallel_start_violations(
    payload: dict[str, Any], state: dict[str, Any], workflow: dict[str, Any]
) -> list[dict[str, str]]:
    """Parallel in-progress admission: concurrency cap, terminal
    dependencies (order is advisory), distinct modules, disjoint test POMs."""
    violations: list[dict[str, str]] = []
    workflow_id = workflow["workflow_id"]
    limit = effective_max_concurrent(payload)
    if len(state["current_workflow_ids"]) >= limit:
        violations.append(
            violation(
                "concurrency-limit-exceeded",
                f"{workflow_id}: in-progress={len(state['current_workflow_ids'])}, limit={limit}",
            )
        )
    for dependency in workflow.get("dependencies", []):
        if (
            state["workflow_statuses"][dependency]["status"]
            not in TERMINAL_WORKFLOW_STATUSES
        ):
            violations.append(
                violation("dependency-not-terminal", f"{workflow_id}: {dependency}")
            )
    build_files = set(workflow["test_build_files"])
    for other_id in state["current_workflow_ids"]:
        other = workflow_by_id(payload, other_id)
        if other["module_id"] == workflow["module_id"]:
            violations.append(
                violation(
                    "module-write-conflict",
                    f"{workflow_id} vs {other_id}: {workflow['module_id']}",
                )
            )
        overlap = build_files & set(other["test_build_files"])
        if overlap:
            violations.append(
                violation(
                    "shared-build-file-conflict",
                    f"{workflow_id} vs {other_id}: {','.join(sorted(overlap))}",
                )
            )
    return violations


def replay_journal(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    state = initial_derived_state(payload)
    violations: list[dict[str, str]] = []
    approval_time = parse_timestamp(payload["selection"]["approved_at"])
    last_time = approval_time
    workflows = {item["workflow_id"]: item for item in payload["workflows"]}
    transitions = payload.get("transitions")
    if not isinstance(transitions, list):
        return state, [violation("invalid-transitions", "transitions must be a list.")]
    for index, event in enumerate(transitions, start=1):
        if not isinstance(event, dict):
            violations.append(violation("invalid-event", str(index)))
            break
        if event.get("revision") != index:
            violations.append(violation("journal-sequence-mismatch", str(index)))
            break
        event_time = parse_timestamp(event.get("at"))
        if event_time is None or (last_time is not None and event_time < last_time):
            violations.append(violation("non-monotonic-event-time", str(index)))
            break
        last_time = event_time
        kind = event.get("event")
        workflow_id = event.get("workflow_id")
        workflow_state = state["workflow_statuses"].get(workflow_id)
        parallel = is_parallel(payload)
        if kind == "boundary-audit":
            expected_actor = (
                state["workflow_writers"].get(workflow_id)
                if parallel
                else state["writer"]
            )
            if event.get("actor") != expected_actor or workflow_state is None:
                violations.append(violation("invalid-audit-event", str(index)))
                break
            state["last_boundary_audit"] = {
                "workflow_id": workflow_id,
                "fingerprint": event.get("audit_fingerprint"),
                "revision": index,
            }
            if parallel:
                state["last_boundary_audits"][workflow_id] = {
                    "fingerprint": event.get("audit_fingerprint"),
                    "revision": index,
                }
        elif kind in {"workflow-transition", "residual-accepted"}:
            if parallel:
                # Per-workflow coupling: the transition consumes the most
                # recent boundary audit for THIS workflow. Any intervening
                # event carrying the same workflow_id replaced or removed the
                # entry, so other workflows' events may interleave freely.
                audit = state["last_boundary_audits"].get(workflow_id)
                if (
                    workflow_state is None
                    or audit is None
                    or audit["fingerprint"] != event.get("audit_fingerprint")
                ):
                    violations.append(violation("audit-not-consumed-in-order", str(index)))
                    break
            else:
                audit = state["last_boundary_audit"]
                if (
                    workflow_state is None
                    or audit is None
                    or audit["workflow_id"] != workflow_id
                    or audit["fingerprint"] != event.get("audit_fingerprint")
                    or audit["revision"] != index - 1
                ):
                    violations.append(violation("audit-not-consumed-in-order", str(index)))
                    break
            source = workflow_state["status"]
            target = event.get("to")
            if kind == "residual-accepted":
                if event.get("actor") != payload["agent_policy"]["coordinator"]:
                    violations.append(violation("invalid-residual-acceptance-event", str(index)))
                    break
                target = "residual-accepted"
            elif event.get("actor") != (
                state["workflow_writers"][workflow_id] if parallel else state["writer"]
            ):
                violations.append(violation("invalid-writer-event", str(index)))
                break
            if target == "in-progress":
                if parallel:
                    if source != "pending" or state["status"] not in {"confirmed", "running"}:
                        violations.append(violation("invalid-workflow-event", str(index)))
                        break
                    start_violations = parallel_start_violations(
                        payload, state, workflows[workflow_id]
                    )
                    if start_violations:
                        violations.extend(start_violations)
                        break
                    workflow_state["status"] = "in-progress"
                    workflow_state["evidence"] = event.get("evidence")
                    state["status"] = "running"
                    state["current_workflow_ids"].append(workflow_id)
                    state["current_workflow_id"] = workflow_id
                else:
                    prior = [
                        item
                        for item in payload["workflows"]
                        if item["order"] < workflows[workflow_id]["order"]
                    ]
                    if (
                        source != "pending"
                        or state["status"] not in {"confirmed", "running"}
                        or state["current_workflow_id"] is not None
                        or any(
                            state["workflow_statuses"][item["workflow_id"]]["status"]
                            not in TERMINAL_WORKFLOW_STATUSES
                            for item in prior
                        )
                    ):
                        violations.append(violation("invalid-workflow-event", str(index)))
                        break
                    workflow_state["status"] = "in-progress"
                    workflow_state["evidence"] = event.get("evidence")
                    state["status"] = "running"
                    state["current_workflow_id"] = workflow_id
                    state["current_workflow_ids"] = [workflow_id]
            elif target in TERMINAL_WORKFLOW_STATUSES:
                # 终态事件（complete / residual-accepted）只能出现在 running 批：
                # paused 批必须先走 batch-resumed 重审协议，不得直接终结工作流。
                if state["status"] != "running":
                    violations.append(violation("invalid-workflow-event", str(index)))
                    break
                if parallel:
                    if source != "in-progress" or workflow_id not in state["current_workflow_ids"]:
                        violations.append(violation("invalid-workflow-event", str(index)))
                        break
                    workflow_state["status"] = target
                    workflow_state["evidence"] = event.get("evidence")
                    state["current_workflow_ids"].remove(workflow_id)
                    state["current_workflow_id"] = (
                        state["current_workflow_ids"][-1]
                        if state["current_workflow_ids"]
                        else None
                    )
                else:
                    if source != "in-progress" or state["current_workflow_id"] != workflow_id:
                        violations.append(violation("invalid-workflow-event", str(index)))
                        break
                    workflow_state["status"] = target
                    workflow_state["evidence"] = event.get("evidence")
                    state["current_workflow_id"] = None
                    state["current_workflow_ids"] = []
                state["status"] = (
                    "complete"
                    if all(
                        item["status"] in TERMINAL_WORKFLOW_STATUSES
                        for item in state["workflow_statuses"].values()
                    )
                    else "running"
                )
            else:
                violations.append(violation("invalid-workflow-event", str(index)))
                break
            if parallel:
                state["last_boundary_audits"].pop(workflow_id, None)
                state["last_boundary_audit"] = most_recent_audit(state)
            else:
                state["last_boundary_audit"] = None
        elif kind == "batch-paused":
            if (
                event.get("actor") != state["writer"]
                or state["status"] not in {"confirmed", "running"}
            ):
                violations.append(violation("invalid-pause-event", str(index)))
                break
            state["pause"] = {
                "reason": event.get("reason"),
                "resume_command": event.get("resume_command"),
                "actor": event.get("actor"),
                "at": event.get("at"),
            }
            state["status"] = "paused"
            state["last_boundary_audit"] = None
            state["last_boundary_audits"] = {}
        elif kind == "batch-resumed":
            audit = state["last_boundary_audit"]
            if parallel:
                # Every in-progress workflow must have re-audited after the
                # pause (pause clears all recorded audits), and the resume
                # event binds the most recent of those audits.
                if (
                    event.get("actor") != state["writer"]
                    or state["status"] != "paused"
                    or audit is None
                    or audit["fingerprint"] != event.get("audit_fingerprint")
                    or any(
                        in_progress_id not in state["last_boundary_audits"]
                        for in_progress_id in state["current_workflow_ids"]
                    )
                ):
                    violations.append(violation("invalid-resume-event", str(index)))
                    break
            elif (
                event.get("actor") != state["writer"]
                or state["status"] != "paused"
                or audit is None
                or audit["revision"] != index - 1
                or audit["fingerprint"] != event.get("audit_fingerprint")
            ):
                violations.append(violation("invalid-resume-event", str(index)))
                break
            state["status"] = "running" if state["current_workflow_ids"] else "confirmed"
            state["pause"] = None
            state["last_boundary_audit"] = None
            state["last_boundary_audits"] = {}
        elif kind == "writer-transferred":
            if event.get("actor") != payload["agent_policy"]["coordinator"]:
                violations.append(violation("invalid-writer-transfer", str(index)))
                break
            if workflow_id is not None:
                if not parallel or workflow_state is None:
                    violations.append(violation("invalid-writer-transfer", str(index)))
                    break
                state["workflow_writers"][workflow_id] = event.get("new_writer")
                state["last_boundary_audits"].pop(workflow_id, None)
                state["last_boundary_audit"] = most_recent_audit(state)
            else:
                state["writer"] = event.get("new_writer")
                state["last_boundary_audit"] = None
                state["last_boundary_audits"] = {}
        elif kind == "batch-invalidated":
            if event.get("actor") != payload["agent_policy"]["coordinator"]:
                violations.append(violation("invalid-invalidation-event", str(index)))
                break
            state["status"] = "needs-reconfirm"
            state["last_boundary_audit"] = None
            state["last_boundary_audits"] = {}
        else:
            violations.append(violation("unknown-event", str(kind)))
            break
        state["revision"] = index
    return state, violations


def selection_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """返回已批准选择契约；运行事件和契约哈希不属于选择内容。"""
    return {
        key: value
        for key, value in payload.items()
        if key not in {"transitions", "selection_contract_sha256"}
    }


def validate_payload(
    payload: Any, run_file: Path, *, allow_unsealed: bool = False
) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    violations, _workflows = base_validation(
        payload, run_file, allow_unsealed=allow_unsealed
    )
    if allow_unsealed or violations or not isinstance(payload, dict):
        return violations, None
    recorded = payload.get("selection_contract_sha256")
    if recorded != canonical_hash(selection_contract(payload)):
        violations.append(
            violation(
                "selection-contract-drift",
                "missing" if recorded is None else str(recorded)[:16],
            )
        )
        return violations, None
    state, replay_violations = replay_journal(payload)
    violations.extend(replay_violations)
    if replay_violations:
        return violations, None
    return violations, state


def append_event(payload: dict[str, Any], event: dict[str, Any]) -> list[dict[str, str]]:
    event = {**event, "revision": len(payload["transitions"]) + 1}
    payload["transitions"].append(event)
    _state, violations = replay_journal(payload)
    return violations


def check_expected_revision(payload: dict[str, Any], expected: int) -> list[dict[str, str]]:
    transitions = payload.get("transitions")
    revision = len(transitions) if isinstance(transitions, list) else -1
    if revision != expected:
        return [
            violation(
                "revision-mismatch",
                f"expected={expected}, actual={revision}",
            )
        ]
    return []


def check_writer(expected_writer: str, actor: str) -> list[dict[str, str]]:
    if actor != expected_writer:
        return [
            violation(
                "writer-lease-mismatch",
                f"active={expected_writer}, actor={actor}",
            )
        ]
    return []


def check_event_time(payload: dict[str, Any], value: str) -> list[dict[str, str]]:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return [violation("invalid-event-time", value)]
    latest = parse_timestamp(payload["selection"]["approved_at"])
    if payload["transitions"]:
        latest = parse_timestamp(payload["transitions"][-1]["at"])
    if latest is not None and timestamp < latest:
        return [violation("non-monotonic-event-time", value)]
    return []


def live_audit_is_current(
    payload: dict[str, Any], state: dict[str, Any], workflow_id: str
) -> list[dict[str, str]]:
    audit = recorded_audit(state, workflow_id, parallel=is_parallel(payload))
    if audit is None:
        return [violation("boundary-audit-required", workflow_id)]
    current, violations = boundary_audit(payload, workflow_id)
    if violations or current is None or current["fingerprint"] != audit.get("fingerprint"):
        details = ", ".join(item["kind"] for item in violations) or "fingerprint changed"
        return [violation("boundary-audit-stale", details), *violations]
    return []


def validate_test_report(path: Path, expected_hash: str) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    if not path.is_file() or file_sha256(path) != expected_hash:
        return [violation("test-report-drift", str(path))]
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return [violation("test-report-invalid", f"{path}: {exc}")]
    suites = [root] if root.tag.endswith("testsuite") else [
        element for element in root if element.tag.endswith("testsuite")
    ]
    if not suites:
        return [violation("test-report-invalid", f"No testsuite: {path}")]
    tests = failures = errors = 0
    try:
        for suite in suites:
            tests += int(suite.attrib.get("tests", "0"))
            failures += int(suite.attrib.get("failures", "0"))
            errors += int(suite.attrib.get("errors", "0"))
    except ValueError:
        return [violation("test-report-invalid", f"Non-numeric totals: {path}")]
    if tests < 1 or failures or errors:
        violations.append(
            violation(
                "test-run-not-clean",
                f"{path}: tests={tests}, failures={failures}, errors={errors}",
            )
        )
    return violations


def validate_test_runs(
    runs: Any, *, expected_count: int | None, allowed_roots: tuple[Path, ...]
) -> list[dict[str, str]]:
    if not isinstance(runs, list) or not runs:
        return [violation("test-runs-missing", str(runs))]
    if expected_count is not None and len(runs) != expected_count:
        return [violation("test-run-count-mismatch", f"expected={expected_count}, actual={len(runs)}")]
    violations: list[dict[str, str]] = []
    seen_run_ids: set[str] = set()
    for run in runs:
        if not isinstance(run, dict) or not nonempty_string(run.get("run_id")) or run["run_id"] in seen_run_ids:
            violations.append(violation("invalid-test-run", str(run)))
            continue
        seen_run_ids.add(run["run_id"])
        reports = run.get("report_files")
        if not isinstance(reports, list) or not reports:
            violations.append(violation("test-reports-missing", run["run_id"]))
            continue
        for report in reports:
            if not isinstance(report, dict):
                violations.append(violation("invalid-test-report", str(report)))
                continue
            path = resolved_path(report.get("path"), allowed_roots[0])
            digest = report.get("sha256")
            if path is None or not any(is_within(path, root) for root in allowed_roots):
                violations.append(violation("test-report-outside-scope", str(report.get("path"))))
            elif not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                violations.append(violation("invalid-test-report-hash", str(digest)))
            else:
                violations.extend(validate_test_report(path, digest))
    return violations


def observed_test_cases(
    runs: Any, *, allowed_roots: tuple[Path, ...]
) -> dict[str, list[tuple[bool, str]]]:
    observed: dict[str, list[tuple[bool, str]]] = {}
    if not isinstance(runs, list):
        return observed
    for run in runs:
        if not isinstance(run, dict) or not isinstance(run.get("report_files"), list):
            continue
        for report in run["report_files"]:
            if not isinstance(report, dict):
                continue
            path = resolved_path(report.get("path"), allowed_roots[0])
            if path is None or not any(is_within(path, root) for root in allowed_roots):
                continue
            try:
                root = ET.parse(path).getroot()
            except (ET.ParseError, OSError):
                continue
            for testcase in root.iter():
                if not testcase.tag.endswith("testcase"):
                    continue
                classname = testcase.attrib.get("classname", "").strip()
                name = testcase.attrib.get("name", "").strip()
                if not classname or not name:
                    continue
                skipped_element = next(
                    (child for child in testcase if child.tag.endswith("skipped")),
                    None,
                )
                skipped = skipped_element is not None
                message = (
                    skipped_element.attrib.get("message", "")
                    if skipped_element is not None
                    else ""
                )
                values = [(skipped, message)]
                for reference in (
                    f"{classname}#{name}",
                    f"{classname.rsplit('.', 1)[-1]}#{name}",
                ):
                    observed.setdefault(reference, []).extend(values)
    return observed


def ticket_id_from_filename(name: str) -> str | None:
    """按统一票据文法从 `issues/<票据ID>[-<slug>].md` 文件名提取票据 ID。"""
    match = re.match(rf"^({TICKET_ID_GRAMMAR})(?:-|\.md$)", name)
    return match.group(1) if match else None


def validate_ticket_test_evidence(
    campaign: Path,
    runs: list[Any],
    *,
    allowed_roots: tuple[Path, ...],
) -> list[dict[str, str]]:
    observed: dict[str, list[tuple[bool, str]]] = {}
    for lane_runs in runs:
        for reference, states in observed_test_cases(
            lane_runs, allowed_roots=allowed_roots
        ).items():
            observed.setdefault(reference, []).extend(states)

    violations: list[dict[str, str]] = []
    issues = campaign / "issues"
    for path in sorted(issues.glob("*.md")) if issues.is_dir() else []:
        ticket_stem = ticket_id_from_filename(path.name)
        if ticket_stem is None:
            violations.append(violation("ticket-id-invalid", path.name))
            continue
        ticket = f"issues/{ticket_stem}"
        content = path.read_text(encoding="utf-8")
        for kind, references in (
            ("characterization", ticket_test_references(content, "characterization-tests")),
            ("regression", ticket_test_references(content, "regression-tests")),
        ):
            for reference in references or []:
                states = observed.get(reference, [])
                if not states:
                    violations.append(
                        violation(
                            "ticket-test-reference-missing",
                            f"{path.name}: {reference}",
                        )
                    )
                    continue
                if kind == "characterization" and not any(
                    not skipped for skipped, _ in states
                ):
                    violations.append(
                        violation(
                            "characterization-test-not-enabled",
                            f"{path.name}: {reference}",
                        )
                    )
                if kind == "regression":
                    matching_skips = [
                        message for skipped, message in states if skipped
                    ]
                    if not matching_skips:
                        violations.append(
                            violation(
                                "regression-test-not-disabled",
                                f"{path.name}: {reference}",
                            )
                        )
                    elif not any(
                        re.search(rf"(?<!\d){re.escape(ticket)}(?!\d)", message)
                        for message in matching_skips
                    ):
                        violations.append(
                            violation(
                                "regression-ticket-mismatch",
                                f"{path.name}: {reference} -> {matching_skips}",
                            )
                        )
    return violations


def validate_terminal_evidence(
    payload: dict[str, Any],
    state: dict[str, Any],
    workflow: dict[str, Any],
    target: str,
    evidence_file: Path,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    violations: list[dict[str, str]] = []
    try:
        evidence_path = evidence_file.expanduser().resolve(strict=True)
        evidence = read_json_file(evidence_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, [violation("terminal-evidence-invalid", str(exc))]
    workspace = Path(payload["workspace_root"]).resolve()
    repository = Path(payload["repository_root"]).resolve()
    worktree = workflow_worktree_path(payload, workflow)
    # Worktree workflows land their docs/tests copies inside their own linked
    # worktree; sequential workflows keep the main repository root.
    docs_root = worktree if worktree is not None else repository
    for key, expected in (
        ("batch_id", payload["batch_id"]),
        ("service", payload["service"]),
        ("workflow_id", workflow["workflow_id"]),
        ("docs_path", workflow["docs_path"]),
        ("production_fix_policy", payload["production_fix_policy"]),
    ):
        if evidence.get(key) != expected:
            violations.append(violation("terminal-evidence-mismatch", key))
    if evidence.get("version") != 1:
        violations.append(violation("terminal-evidence-version", str(evidence.get("version"))))
    campaign = resolved_path(evidence.get("campaign_dir"), workspace)
    expected_campaign = (workspace / workflow["artifact_dir"]).resolve()
    if campaign != expected_campaign or campaign is None or not is_within(campaign, workspace):
        violations.append(violation("campaign-dir-mismatch", str(evidence.get("campaign_dir"))))
    else:
        campaign_result, campaign_exit = validate_campaign(campaign)
        if campaign_exit != 0 or campaign_result.get("campaign_status") != target:
            violations.append(
                violation(
                    "campaign-validation-failed",
                    json.dumps(campaign_result, ensure_ascii=False, sort_keys=True),
                )
            )
    allowed_roots = (workspace, repository)
    violations.extend(
        validate_test_runs(
            evidence.get("unit_test_runs"),
            expected_count=None,
            allowed_roots=allowed_roots,
        )
    )
    integration_runs = evidence.get("integration_test_runs")
    if workflow["integration_lane"] == "required":
        violations.extend(
            validate_test_runs(
                integration_runs,
                expected_count=1,
                allowed_roots=allowed_roots,
            )
        )
    elif integration_runs != []:
        violations.append(violation("integration-applicability-mismatch", str(integration_runs)))
    if campaign is not None:
        violations.extend(
            validate_ticket_test_evidence(
                campaign,
                [evidence.get("unit_test_runs"), integration_runs],
                allowed_roots=allowed_roots,
            )
        )
    copied = evidence.get("copied_artifacts")
    copied_by_source: dict[Path, dict[str, Any]] = {}
    if not isinstance(copied, list):
        violations.append(violation("copied-artifacts-missing", str(copied)))
        copied = []
    for entry in copied:
        if not isinstance(entry, dict):
            violations.append(violation("copied-artifact-invalid", str(entry)))
            continue
        source = resolved_path(entry.get("source"), workspace)
        target_path = resolved_path(entry.get("target"), docs_root)
        digest = entry.get("sha256")
        if source is None or campaign is None or not is_within(source, campaign):
            violations.append(violation("copied-source-invalid", str(entry.get("source"))))
            continue
        expected_docs = (docs_root / workflow["docs_path"]).resolve()
        if target_path is None or not is_within(target_path, expected_docs):
            violations.append(violation("copied-target-invalid", str(entry.get("target"))))
            continue
        if (
            not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or file_sha256(source) != digest
            or file_sha256(target_path) != digest
        ):
            violations.append(violation("copied-artifact-drift", str(source)))
            continue
        copied_by_source[source] = entry
    if campaign is not None:
        required_sources = {
            campaign / "REPORT.md",
            campaign / "BEHAVIOR-MATRIX.md",
            *sorted((campaign / "issues").glob("*.md")),
        }
        missing = sorted(str(path) for path in required_sources - set(copied_by_source))
        if missing:
            violations.append(violation("copied-artifacts-incomplete", ",".join(missing)))
    if violations:
        return None, violations
    return {
        "path": str(evidence_path),
        "sha256": file_sha256(evidence_path),
        "campaign_dir": str(campaign),
    }, []


def validate_acceptance(
    payload: dict[str, Any], state: dict[str, Any], workflow_id: str, acceptance_file: Path
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        path = acceptance_file.expanduser().resolve(strict=True)
        acceptance = read_json_file(path, maximum_size=64 * 1024)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, [violation("residual-acceptance-invalid", str(exc))]
    expected_dir = Path(payload["workspace_root"]).resolve() / ".scratch" / f"{payload['service']}-test-campaign" / "batches" / payload["batch_id"] / "acceptances"
    violations: list[dict[str, str]] = []
    if not is_within(path, expected_dir.resolve()):
        violations.append(violation("residual-acceptance-location", str(path)))
    for key, expected in (
        ("version", 1),
        ("batch_id", payload["batch_id"]),
        ("workflow_id", workflow_id),
        ("scope", "residual-risk-only"),
    ):
        if acceptance.get(key) != expected:
            violations.append(violation("residual-acceptance-mismatch", key))
    risks = acceptance.get("risk_ids")
    if not isinstance(risks, list) or not risks or any(
        not isinstance(risk, str)
        or not re.fullmatch(r"issues/[A-Za-z0-9][A-Za-z0-9-]*", risk)
        for risk in risks
    ):
        violations.append(violation("residual-risk-ids-invalid", str(risks)))
    for key in ("accepted_by", "decision_source"):
        if not nonempty_string(acceptance.get(key)):
            violations.append(violation("residual-acceptance-missing", key))
    if parse_timestamp(acceptance.get("accepted_at")) is None:
        violations.append(violation("residual-acceptance-time", str(acceptance.get("accepted_at"))))
    if violations:
        return None, violations
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "accepted_by": acceptance["accepted_by"],
        "accepted_at": acceptance["accepted_at"],
        "decision_source": acceptance["decision_source"],
        "risk_ids": risks,
    }, []


def invalid_payload(violations: list[dict[str, str]]) -> tuple[dict[str, Any], int]:
    return {"result": "BATCH_INVALID", "violations": violations}, INVALID


def validation_summary(
    payload: dict[str, Any], state: dict[str, Any] | None = None
) -> dict[str, Any]:
    if state is None:
        state, violations = replay_journal(payload)
        if violations:
            raise ValueError(str(violations))
    terminal = sum(
        item["status"] in TERMINAL_WORKFLOW_STATUSES
        for item in state["workflow_statuses"].values()
    )
    return {
        "result": "VALID",
        "batch_id": payload["batch_id"],
        "batch_status": state["status"],
        "selected_workflows": len(payload["workflows"]),
        "terminal_workflows": terminal,
        "current_workflow_id": state["current_workflow_id"],
        "revision": state["revision"],
        "writer": state["writer"],
    }


def workflow_by_id(payload: dict[str, Any], workflow_id: str) -> dict[str, Any] | None:
    return next(
        (workflow for workflow in payload["workflows"] if workflow["workflow_id"] == workflow_id),
        None,
    )


def render(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"result: {payload['result']}")
    for key in sorted(key for key in payload if key != "result"):
        value = payload[key]
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
        print(f"{key}: {rendered}")


def main() -> int:
    args = parse_args()
    requested_run_file = args.run_file.expanduser()
    if not requested_run_file.is_absolute():
        requested_run_file = Path.cwd() / requested_run_file
    run_file = requested_run_file.parent.resolve() / requested_run_file.name
    try:
        if args.command == "validate":
            with run_lock(run_file, exclusive=False):
                payload = read_payload(run_file)
                violations, state = validate_payload(payload, run_file)
            result, exit_code = invalid_payload(violations) if violations else (validation_summary(payload, state), 0)
        elif args.command == "seal":
            with run_lock(run_file, exclusive=True):
                payload = read_payload(run_file)
                violations: list[dict[str, str]] = []
                if isinstance(payload, dict) and nonempty_string(
                    payload.get("selection_contract_sha256")
                ):
                    # Seal the approval once：改动过的选择必须走新批次，不得重封。
                    violations.append(
                        violation(
                            "already-sealed",
                            str(payload["selection_contract_sha256"])[:16],
                        )
                    )
                if not violations:
                    unsealed_violations, _state = validate_payload(
                        payload, run_file, allow_unsealed=True
                    )
                    violations.extend(unsealed_violations)
                if not violations:
                    repository_baseline, baseline_violations = capture_repository_baseline(payload)
                    violations.extend(baseline_violations)
                    if repository_baseline is not None:
                        payload["repository_baseline"] = repository_baseline
                        # seal 一次性校验选定 module 存在于 live Maven reactor；
                        # 错误绑定不得进入已确认批次（否则拖到首次 audit 才爆，
                        # 且批次因选择契约不可改而只能作废重建）。
                        for workflow in payload["workflows"]:
                            module_id = workflow.get("module_id")
                            if module_id != "root" and module_id not in repository_baseline["modules"]:
                                violations.append(
                                    violation(
                                        "workflow-module-unknown",
                                        f"{workflow.get('workflow_id')}: {module_id}",
                                    )
                                )
                if violations:
                    result, exit_code = invalid_payload(violations)
                else:
                    _state, violations = replay_journal(payload)
                    if not violations:
                        payload["selection_contract_sha256"] = canonical_hash(
                            selection_contract(payload)
                        )
                        post_violations, _state = validate_payload(payload, run_file)
                        violations.extend(post_violations)
                    if violations:
                        result, exit_code = invalid_payload(violations)
                    else:
                        atomic_write(run_file, payload)
                        result, exit_code = validation_summary(payload), 0
        else:
            with run_lock(run_file, exclusive=True):
                payload = read_payload(run_file)
                violations, state = validate_payload(payload, run_file)
                violations.extend(check_expected_revision(payload, args.expected_revision))
                violations.extend(check_event_time(payload, args.at))
                if not violations and args.command in {"advance", "audit", "transition", "pause", "resume"}:
                    expected_writer = state["writer"]
                    if is_parallel(payload) and args.command in {"advance", "audit", "transition"}:
                        # Per-workflow writer lease; an unknown workflow is
                        # reported as workflow-not-selected further down.
                        expected_writer = state["workflow_writers"].get(args.workflow)
                    if expected_writer is not None:
                        violations.extend(check_writer(expected_writer, args.actor))
                extra: dict[str, Any] = {}
                if not violations and args.command in {"advance", "audit"}:
                    audit, audit_violations = boundary_audit(payload, args.workflow)
                    violations.extend(audit_violations)
                    if audit is not None and not violations:
                        violations.extend(
                            append_event(
                                payload,
                                {
                                    "event": "boundary-audit",
                                    "workflow_id": args.workflow,
                                    "audit_fingerprint": audit["fingerprint"],
                                    # 只落盘计数：完整 changed_paths 已折叠进
                                    # audit_fingerprint（活体重算比对用的就是它），
                                    # 逐事件内嵌全量路径+哈希会让台账随进度膨胀。
                                    "changed_path_count": len(audit["changed_paths"]),
                                    "actor": args.actor,
                                    "at": args.at,
                                },
                            )
                        )
                        extra["boundary_audit_fingerprint"] = audit["fingerprint"]
                        if args.command == "advance":
                            state, replay_violations = replay_journal(payload)
                            violations.extend(replay_violations)
                if not violations and args.command in {"advance", "transition"}:
                    workflow = workflow_by_id(payload, args.workflow)
                    if workflow is None:
                        violations.append(violation("workflow-not-selected", args.workflow))
                    elif args.to == "residual-accepted":
                        violations.append(violation("residual-acceptance-required", args.workflow))
                    elif args.command == "transition":
                        violations.extend(live_audit_is_current(payload, state, args.workflow))
                    evidence: Any = None
                    if not violations and args.to == "in-progress":
                        if not nonempty_string(args.evidence) or args.evidence_manifest is not None:
                            violations.append(violation("start-evidence-required", str(args.evidence)))
                        else:
                            evidence = args.evidence
                    elif not violations and args.to == "complete":
                        if args.evidence_manifest is None or args.evidence is not None:
                            violations.append(violation("terminal-evidence-required", str(args.evidence_manifest)))
                        else:
                            evidence, evidence_violations = validate_terminal_evidence(
                                payload, state, workflow, "complete", args.evidence_manifest
                            )
                            violations.extend(evidence_violations)
                    if not violations and workflow is not None:
                        parallel = is_parallel(payload)
                        source = state["workflow_statuses"][workflow["workflow_id"]]["status"]
                        if args.to == "in-progress":
                            if state["status"] not in {"confirmed", "running"}:
                                violations.append(
                                    violation(
                                        "invalid-batch-transition",
                                        f"{state['status']}->in-progress",
                                    )
                                )
                            elif parallel:
                                if source != "pending":
                                    violations.append(violation("workflow-out-of-order", args.workflow))
                                else:
                                    violations.extend(
                                        parallel_start_violations(payload, state, workflow)
                                    )
                            else:
                                prior = [
                                    item for item in payload["workflows"] if item["order"] < workflow["order"]
                                ]
                                if (
                                    source != "pending"
                                    or state["current_workflow_id"] is not None
                                    or any(
                                        state["workflow_statuses"][item["workflow_id"]]["status"]
                                        not in TERMINAL_WORKFLOW_STATUSES
                                        for item in prior
                                    )
                                ):
                                    violations.append(violation("workflow-out-of-order", args.workflow))
                        elif state["status"] != "running":
                            violations.append(
                                violation(
                                    "invalid-batch-transition",
                                    f"{state['status']}->{args.to}",
                                )
                            )
                        elif parallel:
                            if source != "in-progress" or args.workflow not in state["current_workflow_ids"]:
                                violations.append(violation("invalid-workflow-transition", f"{source}->{args.to}"))
                        elif source != "in-progress" or state["current_workflow_id"] != args.workflow:
                            violations.append(violation("invalid-workflow-transition", f"{source}->{args.to}"))
                    if not violations:
                        violations.extend(
                            append_event(
                                payload,
                                {
                                    "event": "workflow-transition",
                                    "workflow_id": args.workflow,
                                    "from": state["workflow_statuses"][workflow["workflow_id"]]["status"],
                                    "to": args.to,
                                    "audit_fingerprint": bound_audit_fingerprint(
                                        payload, state, args.workflow
                                    ),
                                    "evidence": evidence,
                                    "actor": args.actor,
                                    "at": args.at,
                                },
                            )
                        )
                elif not violations and args.command == "pause":
                    if state["status"] not in {"confirmed", "running"}:
                        violations.append(violation("invalid-batch-transition", f"{state['status']}->paused"))
                    if not violations:
                        violations.extend(
                            append_event(
                                payload,
                                {
                                    "event": "batch-paused",
                                    "reason": args.reason,
                                    "resume_command": args.resume_command,
                                    "actor": args.actor,
                                    "at": args.at,
                                },
                            )
                        )
                elif not violations and args.command == "resume":
                    workflow_id = None
                    if state["status"] != "paused":
                        violations.append(violation("invalid-batch-transition", f"{state['status']}->running"))
                    elif is_parallel(payload):
                        if not state["current_workflow_ids"] and state["last_boundary_audit"] is None:
                            violations.append(
                                violation(
                                    "resume-without-active-audit",
                                    "audit the next workflow before resuming an idle batch",
                                )
                            )
                        elif state["current_workflow_ids"]:
                            # Re-verify a fresh live audit for EVERY in-progress
                            # workflow before the batch leaves paused state.
                            for in_progress_id in state["current_workflow_ids"]:
                                violations.extend(
                                    live_audit_is_current(payload, state, in_progress_id)
                                )
                        else:
                            workflow_id = state["last_boundary_audit"]["workflow_id"]
                            violations.extend(live_audit_is_current(payload, state, workflow_id))
                    elif state["current_workflow_id"] is None and state["last_boundary_audit"] is None:
                        # Paused while idle, before any workflow audit: there is no
                        # boundary to re-verify. Return a clean violation instead of
                        # dereferencing a null last_boundary_audit.
                        violations.append(
                            violation(
                                "resume-without-active-audit",
                                "audit the next workflow before resuming an idle batch",
                            )
                        )
                    else:
                        workflow_id = state["current_workflow_id"] or state["last_boundary_audit"]["workflow_id"]
                        violations.extend(live_audit_is_current(payload, state, workflow_id))
                    if not violations:
                        violations.extend(
                            append_event(
                                payload,
                                {
                                    "event": "batch-resumed",
                                    "workflow_id": workflow_id,
                                    "audit_fingerprint": state["last_boundary_audit"]["fingerprint"],
                                    "actor": args.actor,
                                    "at": args.at,
                                },
                            )
                        )
                elif not violations and args.command == "accept-residual":
                    if args.actor != payload["agent_policy"]["coordinator"]:
                        violations.append(violation("coordinator-mismatch", args.actor))
                    workflow = workflow_by_id(payload, args.workflow)
                    if workflow is None:
                        violations.append(violation("workflow-not-selected", args.workflow))
                    else:
                        audit, audit_violations = boundary_audit(payload, args.workflow)
                        violations.extend(audit_violations)
                        if audit is not None and not violations:
                            violations.extend(
                                append_event(
                                    payload,
                                    {
                                        "event": "boundary-audit",
                                        "workflow_id": args.workflow,
                                        "audit_fingerprint": audit["fingerprint"],
                                        "changed_path_count": len(audit["changed_paths"]),
                                        "actor": args.actor,
                                        "at": args.at,
                                    },
                                )
                            )
                            state, replay_violations = replay_journal(payload)
                            violations.extend(replay_violations)
                        # 与 transition 终态门禁对称：paused / needs-reconfirm 批
                        # 必须先 resume，不得直接接受剩余风险。
                        source = state["workflow_statuses"][workflow["workflow_id"]]["status"]
                        if state["status"] != "running":
                            violations.append(
                                violation(
                                    "invalid-batch-transition",
                                    f"{state['status']}->residual-accepted",
                                )
                            )
                        elif is_parallel(payload):
                            if (
                                source != "in-progress"
                                or args.workflow not in state["current_workflow_ids"]
                            ):
                                violations.append(
                                    violation(
                                        "invalid-workflow-transition",
                                        f"{source}->residual-accepted",
                                    )
                                )
                        elif (
                            source != "in-progress"
                            or state["current_workflow_id"] != args.workflow
                        ):
                            violations.append(
                                violation(
                                    "invalid-workflow-transition",
                                    f"{source}->residual-accepted",
                                )
                            )
                    evidence = acceptance = None
                    if not violations:
                        evidence, evidence_violations = validate_terminal_evidence(
                            payload, state, workflow, "residual-accepted", args.evidence_manifest
                        )
                        acceptance, acceptance_violations = validate_acceptance(
                            payload, state, args.workflow, args.acceptance_file
                        )
                        violations.extend(evidence_violations + acceptance_violations)
                        if acceptance is not None:
                            accepted_at = parse_timestamp(acceptance["accepted_at"])
                            approved_at = parse_timestamp(
                                payload["selection"]["approved_at"]
                            )
                            event_at = parse_timestamp(args.at)
                            if (
                                accepted_at is None
                                or approved_at is None
                                or event_at is None
                                or accepted_at < approved_at
                                or accepted_at > event_at
                            ):
                                violations.append(
                                    violation(
                                        "residual-acceptance-time",
                                        acceptance["accepted_at"],
                                    )
                                )
                    if not violations:
                        violations.extend(
                            append_event(
                                payload,
                                {
                                    "event": "residual-accepted",
                                    "workflow_id": args.workflow,
                                    "from": state["workflow_statuses"][workflow["workflow_id"]]["status"],
                                    "to": "residual-accepted",
                                    "audit_fingerprint": bound_audit_fingerprint(
                                        payload, state, args.workflow
                                    ),
                                    "evidence": evidence,
                                    "acceptance": acceptance,
                                    "actor": args.actor,
                                    "at": args.at,
                                },
                            )
                        )
                elif not violations and args.command == "transfer-writer":
                    if args.actor != payload["agent_policy"]["coordinator"]:
                        violations.append(violation("coordinator-mismatch", args.actor))
                    if args.workflow is not None:
                        # Per-workflow writer reassignment (parallel mode only):
                        # coordinator-gated and journaled with the workflow_id.
                        if not is_parallel(payload):
                            violations.append(
                                violation(
                                    "invalid-writer-transfer",
                                    "--workflow requires execution_mode parallel",
                                )
                            )
                        elif workflow_by_id(payload, args.workflow) is None:
                            violations.append(violation("workflow-not-selected", args.workflow))
                        elif (
                            not nonempty_string(args.new_writer)
                            or args.new_writer == state["workflow_writers"][args.workflow]
                        ):
                            violations.append(violation("invalid-new-writer", args.new_writer))
                        if not violations:
                            violations.extend(
                                append_event(
                                    payload,
                                    {
                                        "event": "writer-transferred",
                                        "workflow_id": args.workflow,
                                        "old_writer": state["workflow_writers"][args.workflow],
                                        "new_writer": args.new_writer,
                                        "reason": args.reason,
                                        "actor": args.actor,
                                        "at": args.at,
                                    },
                                )
                            )
                            extra["workflow"] = args.workflow
                            extra["workflow_writer"] = args.new_writer
                    else:
                        if not nonempty_string(args.new_writer) or args.new_writer == state["writer"]:
                            violations.append(violation("invalid-new-writer", args.new_writer))
                        if not violations:
                            violations.extend(
                                append_event(
                                    payload,
                                    {
                                        "event": "writer-transferred",
                                        "old_writer": state["writer"],
                                        "new_writer": args.new_writer,
                                        "reason": args.reason,
                                        "actor": args.actor,
                                        "at": args.at,
                                    },
                                )
                            )
                            extra["writer"] = args.new_writer
                elif not violations and args.command == "invalidate":
                    if args.actor != payload["agent_policy"]["coordinator"]:
                        violations.append(violation("coordinator-mismatch", args.actor))
                    if not violations:
                        violations.extend(
                            append_event(
                                payload,
                                {
                                    "event": "batch-invalidated",
                                    "reason": args.reason,
                                    "evidence": args.evidence,
                                    "actor": args.actor,
                                    "at": args.at,
                                },
                            )
                        )
                if violations:
                    result, exit_code = invalid_payload(violations)
                else:
                    # append_event 已重放并验证 journal；这里只原子持久化事件。
                    atomic_write(run_file, payload)
                    result = {**validation_summary(payload), **extra}
                    exit_code = 0
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
        # 畸形 run 文件缺键/类型错乱必须以结构化 BATCH_INVALID 报错，
        # 而不是把 Python traceback 泄露给调用方。
        KeyError,
        TypeError,
        ET.ParseError,
        target_preflight.PreflightError,
    ) as exc:
        result, exit_code = invalid_payload([violation("io-or-format-error", str(exc))])
    render(result, args.format)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
