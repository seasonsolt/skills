#!/usr/bin/env python3
"""只读校验任意 Java/Maven 仓库的存量测试加固入口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


USER_DECISION_REQUIRED = 2
HARD_BLOCK = 3


class PreflightError(Exception):
    def __init__(self, result: str, message: str, exit_code: int, **facts: Any) -> None:
        super().__init__(message)
        self.result = result
        self.message = message
        self.exit_code = exit_code
        self.facts = facts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="只读校验目标仓库、外置 campaign 工作区、Git 状态与 Maven 模块。"
    )
    parser.add_argument(
        "--repository-root", required=True, type=Path, help="目标 Git 仓库根目录"
    )
    parser.add_argument(
        "--campaign-workspace",
        required=True,
        type=Path,
        help="位于目标仓库之外、用于保存 .scratch campaign 的目录",
    )
    parser.add_argument(
        "--service-id",
        help="稳定的 campaign 标识；默认使用仓库目录名",
    )
    parser.add_argument("--module", help="多模块 Maven 仓库中的目标模块")
    parser.add_argument(
        "--service-campaign",
        action="store_true",
        help="按 service campaign 校验整仓，后续批次再绑定 workflow 与模块",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式（默认 text）",
    )
    return parser.parse_args()


def git(repository_root: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PreflightError("GIT_INVALID", f"Git 校验失败：{detail}", HARD_BLOCK)
    return completed.stdout.rstrip("\r\n")


def git_optional(repository_root: Path, *arguments: str) -> str | None:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def sanitized_repository_url(value: str | None) -> str | None:
    """返回可安全展示的 origin，移除 URL 用户信息、查询参数与 fragment。"""
    if not value:
        return value
    if "://" in value:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return parsed._replace(netloc=host, query="", fragment="").geturl()
    scp_match = re.fullmatch(r"(?:[^@]+@)?([^:]+):(.+)", value)
    if scp_match:
        return f"{scp_match.group(1)}:{scp_match.group(2)}"
    return value


def display_git_path(raw_path: bytes) -> str:
    return raw_path.decode("utf-8", errors="backslashreplace")


def tracked_state(repository_root: Path) -> tuple[list[str], list[str]]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    output = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=no"],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if output.returncode != 0:
        detail = output.stderr.decode(errors="replace").strip()
        raise PreflightError(
            "GIT_INVALID", f"Git 状态校验失败：{detail}", HARD_BLOCK
        )

    changes: list[str] = []
    conflicts: list[str] = []
    records = output.stdout.split(b"\0")
    index = 0
    conflict_statuses = {b"DD", b"AU", b"UD", b"UA", b"DU", b"AA", b"UU"}
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        status = record[:2]
        paths = [display_git_path(record[3:])]
        if (
            status[:1] in {b"R", b"C"} or status[1:2] in {b"R", b"C"}
        ) and index < len(records):
            source = records[index]
            index += 1
            if source:
                paths.append(display_git_path(source))
        changes.extend(paths)
        if status in conflict_statuses or b"U" in status:
            conflicts.extend(paths)
    return sorted(set(changes)), sorted(set(conflicts))


def untracked_files(repository_root: Path) -> list[str]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    output = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if output.returncode != 0:
        detail = output.stderr.decode(errors="replace").strip()
        raise PreflightError(
            "GIT_INVALID", f"Git 未跟踪文件校验失败：{detail}", HARD_BLOCK
        )
    return sorted(display_git_path(item) for item in output.stdout.split(b"\0") if item)


def _direct_modules(pom: Path, *, strict: bool) -> list[str]:
    """返回一个 POM 直接声明的 module；根 POM 解析错误时硬阻断。"""
    try:
        root = ET.parse(pom).getroot()
    except ET.ParseError as exc:
        if strict:
            raise PreflightError(
                "MAVEN_INVALID", f"pom.xml 无法解析：{exc}", HARD_BLOCK
            ) from exc
        return []

    modules: list[str] = []
    for element in root:
        if element.tag.rsplit("}", 1)[-1] != "modules":
            continue
        for child in element:
            if (
                child.tag.rsplit("}", 1)[-1] == "module"
                and child.text
                and child.text.strip()
            ):
                module = child.text.strip()
                if Path(module).is_absolute():
                    raise PreflightError(
                        "MAVEN_INVALID",
                        f"pom.xml 的 module 不能是绝对路径：{module}",
                        HARD_BLOCK,
                    )
                modules.append(module)
    return list(dict.fromkeys(modules))


def maven_modules(pom: Path) -> list[str]:
    """递归展开 Maven reactor，返回仓库根相对 module 路径。"""
    repository_root = pom.parent
    collected: list[str] = []
    seen_paths: set[str] = set()
    visited_dirs: set[Path] = set()
    try:
        visited_dirs.add(repository_root.resolve())
    except OSError:
        pass

    def walk(current_pom: Path, prefix: str, *, strict: bool) -> None:
        for name in _direct_modules(current_pom, strict=strict):
            raw = f"{prefix}/{name}" if prefix else name
            relative = posixpath.normpath(raw)
            if (
                Path(relative).is_absolute()
                or relative in {".", ".."}
                or relative.startswith("../")
            ):
                raise PreflightError(
                    "MAVEN_INVALID",
                    f"pom.xml 的 module 不能越出仓库：{raw}",
                    HARD_BLOCK,
                )
            if relative in seen_paths:
                continue
            seen_paths.add(relative)
            collected.append(relative)
            module_dir = repository_root / relative
            child_pom = module_dir / "pom.xml"
            if not child_pom.is_file():
                continue
            try:
                resolved = module_dir.resolve()
            except OSError:
                continue
            if resolved in visited_dirs:
                continue
            visited_dirs.add(resolved)
            walk(child_pom, relative, strict=False)

    walk(pom, "", strict=True)
    return collected


def validate_maven_module_root(
    repository_root: Path,
    module: str,
    *,
    invalid_result: str,
    exit_code: int,
) -> Path:
    module_root = (repository_root / module).resolve()
    try:
        module_root.relative_to(repository_root)
    except ValueError as exc:
        raise PreflightError(
            "MAVEN_INVALID",
            f"模块解析后越出目标仓库：{module}",
            HARD_BLOCK,
        ) from exc
    if not (module_root / "pom.xml").is_file():
        raise PreflightError(
            invalid_result,
            f"模块缺少 pom.xml：{module}",
            exit_code,
        )
    module_repository_root = Path(
        git(module_root, "rev-parse", "--show-toplevel")
    ).resolve()
    if module_repository_root != repository_root:
        raise PreflightError(
            "MAVEN_INVALID",
            f"模块不属于目标 Git 仓库：{module}",
            HARD_BLOCK,
        )
    return module_root


def git_operation_markers(repository_root: Path) -> list[str]:
    markers = (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "BISECT_LOG",
        "rebase-apply",
        "rebase-merge",
        "sequencer",
    )
    active: list[str] = []
    for marker in markers:
        raw_path = git(repository_root, "rev-parse", "--git-path", marker)
        marker_path = Path(raw_path)
        if not marker_path.is_absolute():
            marker_path = repository_root / marker_path
        if marker_path.exists():
            active.append(marker)
    return active


def path_content_digest(repository_root: Path, relative_path: str) -> tuple[str, str]:
    path = repository_root / relative_path
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return "missing", hashlib.sha256(b"missing").hexdigest()
    digest = hashlib.sha256()
    if stat.S_ISLNK(metadata.st_mode):
        digest.update(b"symlink\0")
        digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        return "symlink", digest.hexdigest()
    if stat.S_ISREG(metadata.st_mode):
        digest.update(b"file\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return "file", digest.hexdigest()
    digest.update(f"mode:{metadata.st_mode}".encode("ascii"))
    return "other", digest.hexdigest()


def git_path_index_facts(
    repository_root: Path, relative_path: str
) -> tuple[str, str | None]:
    environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    status_result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            relative_path,
        ],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if status_result.returncode != 0:
        raise PreflightError(
            "GIT_INVALID", f"无法读取路径状态：{relative_path}", HARD_BLOCK
        )
    first_record = status_result.stdout.split(b"\0", 1)[0]
    git_status = (
        first_record[:2].decode("ascii", errors="replace")
        if len(first_record) >= 2
        else ""
    )
    index_result = subprocess.run(
        ["git", "ls-files", "--stage", "-z", "--", relative_path],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if index_result.returncode != 0:
        raise PreflightError(
            "GIT_INVALID", f"无法读取 index 路径：{relative_path}", HARD_BLOCK
        )
    first_index_record = index_result.stdout.split(b"\0", 1)[0]
    index_oid: str | None = None
    if first_index_record:
        metadata = first_index_record.split(b"\t", 1)[0].split()
        if len(metadata) >= 2:
            index_oid = metadata[1].decode("ascii", errors="replace")
    return git_status, index_oid


def bulk_git_path_index_facts(
    repository_root: Path, relative_paths: list[str]
) -> dict[str, tuple[str, str | None]]:
    """用两个 Git 进程批量读取所有路径的状态与 index OID。"""
    environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    status_result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--no-renames",
        ],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if status_result.returncode != 0:
        raise PreflightError("GIT_INVALID", "无法批量读取路径状态", HARD_BLOCK)
    statuses: dict[str, str] = {}
    for record in status_result.stdout.split(b"\0"):
        if len(record) < 4:
            continue
        statuses[display_git_path(record[3:])] = record[:2].decode(
            "ascii", errors="replace"
        )
    index_result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if index_result.returncode != 0:
        raise PreflightError("GIT_INVALID", "无法批量读取 index 路径", HARD_BLOCK)
    index_oids: dict[str, str] = {}
    for record in index_result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, _, raw_path = record.partition(b"\t")
        fields = metadata.split()
        if len(fields) >= 2 and raw_path:
            index_oids[display_git_path(raw_path)] = fields[1].decode(
                "ascii", errors="replace"
            )
    return {
        path: (statuses.get(path, ""), index_oids.get(path))
        for path in relative_paths
    }


def is_campaign_resume(backlog: Path, branch: str) -> bool:
    if not backlog.is_file():
        return False
    lines = backlog.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if branch in cells and "in-progress" in cells:
            return True
    return False


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def inspect(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    requested_root = args.repository_root.expanduser().resolve()
    if not requested_root.is_dir():
        raise PreflightError(
            "REPOSITORY_INVALID",
            f"目标目录不存在：{requested_root}",
            HARD_BLOCK,
        )

    top_level = git_optional(requested_root, "rev-parse", "--show-toplevel")
    if not top_level:
        raise PreflightError(
            "REPOSITORY_INVALID",
            f"目标不是 Git 仓库：{requested_root}",
            HARD_BLOCK,
        )
    repository_root = Path(top_level).resolve()
    if repository_root != requested_root:
        raise PreflightError(
            "REPOSITORY_NOT_ROOT",
            "--repository-root 必须精确指向 Git 仓库根目录",
            USER_DECISION_REQUIRED,
            requested_repository_root=str(requested_root),
            repository_root=str(repository_root),
        )
    if not (repository_root / "pom.xml").is_file():
        raise PreflightError(
            "UNSUPPORTED_PROJECT",
            "目标仓库根目录缺少 pom.xml，不是受支持的 Java/Maven 仓库",
            HARD_BLOCK,
            repository_root=str(repository_root),
        )

    service_id = args.service_id or repository_root.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", service_id) or service_id in {
        ".",
        "..",
    }:
        raise PreflightError(
            "SERVICE_ID_REQUIRED",
            "仓库目录名不能安全用作 campaign 标识；请显式传入 --service-id",
            USER_DECISION_REQUIRED,
            repository_name=repository_root.name,
        )

    campaign_workspace = args.campaign_workspace.expanduser().resolve()
    if not campaign_workspace.is_dir():
        raise PreflightError(
            "CAMPAIGN_WORKSPACE_INVALID",
            f"campaign 工作区不存在：{campaign_workspace}",
            HARD_BLOCK,
            campaign_workspace=str(campaign_workspace),
        )
    if is_within(campaign_workspace, repository_root):
        raise PreflightError(
            "CAMPAIGN_WORKSPACE_INSIDE_REPOSITORY",
            "campaign 工作区必须位于目标仓库之外，避免证据污染仓库状态",
            HARD_BLOCK,
            campaign_workspace=str(campaign_workspace),
            repository_root=str(repository_root),
        )
    campaign_root = (
        campaign_workspace / ".scratch" / f"{service_id}-test-campaign"
    ).resolve()
    if is_within(campaign_root, repository_root):
        raise PreflightError(
            "CAMPAIGN_WORKSPACE_INSIDE_REPOSITORY",
            "解析后的 campaign 路径位于目标仓库内",
            HARD_BLOCK,
            campaign_root=str(campaign_root),
            repository_root=str(repository_root),
        )
    if args.service_campaign and args.module:
        raise PreflightError(
            "MODULE_SCOPE_CONFLICT",
            "service campaign 入口不能同时绑定单个 Maven 模块",
            USER_DECISION_REQUIRED,
            target_scope="service-campaign",
            module=args.module,
        )

    branch = git(repository_root, "branch", "--show-current")
    if not branch:
        branch = f"DETACHED@{git(repository_root, 'rev-parse', '--short', 'HEAD')}"
    baseline = git(repository_root, "rev-parse", "HEAD")
    tracked, conflicts = tracked_state(repository_root)
    untracked = untracked_files(repository_root)
    backlog = campaign_root / "BACKLOG.md"
    resume_candidate = is_campaign_resume(backlog, branch)
    common_facts = {
        "service": service_id,
        "repository_root": str(repository_root),
        "campaign_workspace": str(campaign_workspace),
        "campaign_root": str(campaign_root),
        "branch": branch,
        "baseline": baseline,
        "tracked_changes": tracked,
        "untracked_files": untracked,
        "resume_candidate": resume_candidate,
    }
    if conflicts:
        raise PreflightError(
            "GIT_CONFLICT",
            "目标仓库存在未解决的 merge 冲突；必须先完成或中止冲突处理",
            HARD_BLOCK,
            conflicted_files=conflicts,
            **common_facts,
        )
    active_operations = git_operation_markers(repository_root)
    if active_operations:
        raise PreflightError(
            "GIT_OPERATION_IN_PROGRESS",
            "目标仓库存在未结束的 Git 操作；必须先完成或中止",
            HARD_BLOCK,
            git_operation_markers=active_operations,
            **common_facts,
        )
    if tracked or untracked:
        raise PreflightError(
            "WORKTREE_NOT_CLEAN",
            "测试加固 campaign 必须从专用且完全干净的 worktree 启动",
            HARD_BLOCK,
            **common_facts,
        )

    modules = maven_modules(repository_root / "pom.xml")
    selected_module = args.module
    target_scope = "service-campaign" if args.service_campaign else "module"
    if selected_module and selected_module not in modules:
        raise PreflightError(
            "MODULE_INVALID",
            f"模块不在根 pom.xml 的 reactor 中：{selected_module}",
            USER_DECISION_REQUIRED,
            modules=modules,
            **common_facts,
        )
    if args.service_campaign:
        for module in modules:
            validate_maven_module_root(
                repository_root,
                module,
                invalid_result="MAVEN_INVALID",
                exit_code=HARD_BLOCK,
            )
    if selected_module:
        validate_maven_module_root(
            repository_root,
            selected_module,
            invalid_result="MODULE_INVALID",
            exit_code=USER_DECISION_REQUIRED,
        )
    if modules and not selected_module and not args.service_campaign:
        raise PreflightError(
            "MODULE_SELECTION_REQUIRED",
            "目标是多模块 Maven 仓库；请选择一个模块或使用 --service-campaign",
            USER_DECISION_REQUIRED,
            modules=modules,
            module=None,
            target_scope=target_scope,
            **common_facts,
        )

    origin_url = sanitized_repository_url(
        git_optional(repository_root, "remote", "get-url", "origin")
    )
    return (
        {
            "result": "READY",
            "message": "只读预检通过；下一步仍需读取仓库规范、建立核心流证据并让用户确认批次。",
            **common_facts,
            "module": selected_module,
            "modules": modules,
            "target_scope": target_scope,
            "origin_url": origin_url,
            "repository_identity_verified": True,
            "repository_identity_reason": "用户显式提供的 real path 与 Git top-level 一致",
        },
        0,
    )


def render(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"结果: {payload['result']}")
    if payload.get("message"):
        print(f"说明: {payload['message']}")
    for key in sorted(key for key in payload if key not in {"result", "message"}):
        value = payload[key]
        if value not in (None, "", []):
            rendered = (
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, (list, dict))
                else value
            )
            print(f"{key}: {rendered}")


def main() -> int:
    args = parse_args()
    try:
        payload, exit_code = inspect(args)
    except PreflightError as exc:
        payload = {
            "result": exc.result,
            "message": exc.message,
            "service": args.service_id,
            **exc.facts,
        }
        exit_code = exc.exit_code
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        payload = {
            "result": "INTERNAL_ERROR",
            "message": f"预检无法稳定解析本地事实：{type(exc).__name__}: {exc}",
            "service": args.service_id,
        }
        exit_code = HARD_BLOCK
    render(payload, args.format)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
