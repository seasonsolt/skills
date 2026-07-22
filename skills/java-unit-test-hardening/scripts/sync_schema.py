#!/usr/bin/env python3
"""Read a datasource URL from stdin and atomically export a schema-only snapshot."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


HARD_BLOCK = 3


class SyncError(Exception):
    def __init__(self, result: str, message: str, **facts: Any) -> None:
        super().__init__(message)
        self.result = result
        self.message = message
        self.facts = facts


@dataclass(frozen=True)
class Datasource:
    dialect: str
    host: str
    port: int
    database: str
    username: str
    password: str | None
    options: dict[str, str]

    @property
    def redacted_identity(self) -> str:
        return f"{self.dialect}://{self.host}:{self.port}/{self.database}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 stdin 读取 datasource/JDBC URL，并只读导出数据库结构快照。"
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="目标服务 Git 仓库根目录（默认当前目录）",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="输出格式"
    )
    return parser.parse_args()


def read_datasource_url() -> str:
    if sys.stdin.isatty():
        value = getpass.getpass("Datasource URL（输入内容不会显示）: ")
    else:
        value = sys.stdin.readline()
    value = value.strip()
    if not value:
        raise SyncError("DATASOURCE_URL_REQUIRED", "未从 stdin 读取到 datasource URL")
    return value


def single_query_value(query: dict[str, list[str]], *names: str) -> str | None:
    lowered = {key.lower(): values for key, values in query.items()}
    for name in names:
        values = lowered.get(name.lower())
        if values and values[-1]:
            return values[-1]
    return None


def parse_datasource(raw_url: str) -> Datasource:
    normalized = raw_url[5:] if raw_url.lower().startswith("jdbc:") else raw_url
    parsed = urlsplit(normalized)
    aliases = {
        "mysql": "mysql",
        "mariadb": "mariadb",
        "postgres": "postgresql",
        "postgresql": "postgresql",
    }
    dialect = aliases.get(parsed.scheme.lower())
    if dialect is None:
        raise SyncError(
            "UNSUPPORTED_DATASOURCE",
            "仅支持 MySQL、MariaDB 和 PostgreSQL datasource/JDBC URL",
        )
    if not parsed.hostname:
        raise SyncError("DATASOURCE_INVALID", "datasource URL 缺少 host")
    query = parse_qs(parsed.query, keep_blank_values=True)
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    username = username or single_query_value(query, "user", "username")
    password = password or single_query_value(query, "password")
    if not username:
        raise SyncError("DATASOURCE_INVALID", "datasource URL 必须包含只读数据库用户名")
    database = unquote(parsed.path.lstrip("/").split("/", 1)[0])
    # 首字符禁用连字符：`-xxx` 会被 mysqldump/mariadb-dump 解析成命令行选项
    # （参数注入），破坏只读单库承诺。
    if not database or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", database):
        raise SyncError("DATASOURCE_INVALID", "数据库名缺失或包含不安全字符")
    default_port = 5432 if dialect == "postgresql" else 3306
    try:
        port = parsed.port or default_port
    except ValueError as exc:
        raise SyncError("DATASOURCE_INVALID", "datasource URL 端口无效") from exc
    options = {
        key.lower(): values[-1]
        for key, values in query.items()
        if values and values[-1]
    }
    return Datasource(
        dialect=dialect,
        host=parsed.hostname,
        port=port,
        database=database,
        username=username,
        password=password,
        options=options,
    )


def resolve_repository_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if not root.is_dir() or not (root / "pom.xml").is_file():
        message = "目标必须是包含根 pom.xml 的 Java/Maven 仓库"
        raise SyncError("REPOSITORY_INVALID", message)
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if completed.returncode != 0:
        raise SyncError("REPOSITORY_INVALID", "目标目录不是 Git 仓库")
    if Path(completed.stdout.strip()).resolve() != root:
        raise SyncError("REPOSITORY_INVALID", "目标路径必须是独立 Git 仓库根目录")
    return root


def ensure_snapshot_is_safe_to_replace(root: Path, relative_path: Path) -> None:
    completed = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            relative_path.as_posix(),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if completed.returncode != 0:
        raise SyncError("GIT_INVALID", "无法校验 schema 快照的 Git 状态")
    if completed.stdout.strip():
        raise SyncError(
            "SNAPSHOT_DIRTY",
            "目标 schema 快照已有未提交改动；为避免覆盖，已停止同步",
            output_path=str(root / relative_path),
        )


def resolve_dump_client(
    datasource: Datasource,
) -> tuple[str, list[str], dict[str, str]]:
    environment: dict[str, str] = {}
    if datasource.dialect in {"mysql", "mariadb"}:
        candidates = (
            ("mariadb-dump", "mysqldump")
            if datasource.dialect == "mariadb"
            else ("mysqldump", "mariadb-dump")
        )
        executable = next(
            (resolved for name in candidates if (resolved := shutil.which(name))),
            None,
        )
        if executable is None:
            raise SyncError(
                "DUMP_CLIENT_MISSING",
                f"缺少数据库导出客户端：{' 或 '.join(candidates)}",
            )
        arguments = [
            "--no-data",
            "--skip-comments",
            "--skip-lock-tables",
            "--no-tablespaces",
            "--set-gtid-purged=OFF",
            f"--host={datasource.host}",
            f"--port={datasource.port}",
            f"--user={datasource.username}",
        ]
        ssl_mode = datasource.options.get("sslmode")
        if ssl_mode:
            arguments.append(f"--ssl-mode={ssl_mode.upper()}")
        elif datasource.options.get("requiressl", "").lower() == "true":
            arguments.append("--ssl-mode=REQUIRED")
        elif datasource.options.get("usessl", "").lower() == "false":
            arguments.append("--ssl-mode=DISABLED")
        arguments.append(datasource.database)
        if datasource.password is not None:
            environment["MYSQL_PWD"] = datasource.password
        return executable, arguments, environment

    executable = shutil.which("pg_dump")
    if executable is None:
        raise SyncError("DUMP_CLIENT_MISSING", "缺少数据库导出客户端：pg_dump")
    arguments = [
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--host",
        datasource.host,
        "--port",
        str(datasource.port),
        "--username",
        datasource.username,
        "--dbname",
        datasource.database,
    ]
    if datasource.password is not None:
        environment["PGPASSWORD"] = datasource.password
    ssl_mode = datasource.options.get("sslmode")
    if ssl_mode:
        environment["PGSSLMODE"] = ssl_mode
    elif datasource.options.get("ssl", "").lower() == "true":
        environment["PGSSLMODE"] = "require"
    return executable, arguments, environment


def export_schema(root: Path, datasource: Datasource) -> tuple[Path, str, str]:
    relative_path = Path("db") / "schema" / f"{datasource.database}.sql"
    ensure_snapshot_is_safe_to_replace(root, relative_path)
    output_path = root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    executable, arguments, secret_environment = resolve_dump_client(datasource)
    environment = os.environ.copy()
    environment.update(secret_environment)
    completed = subprocess.run(
        [executable, *arguments],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SyncError(
            "SCHEMA_EXPORT_FAILED",
            f"schema-only 导出失败，客户端退出码 {completed.returncode}",
            client=Path(executable).name,
            datasource=datasource.redacted_identity,
        )
    if not completed.stdout.strip():
        raise SyncError(
            "SCHEMA_EXPORT_EMPTY",
            "数据库客户端没有返回 schema 内容",
            client=Path(executable).name,
            datasource=datasource.redacted_identity,
        )
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=output_path.parent, prefix=f".{output_path.name}.", delete=False
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(completed.stdout)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    digest = hashlib.sha256(completed.stdout).hexdigest()
    return output_path, digest, Path(executable).name


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
            print(f"{key}: {value}")


def main() -> int:
    args = parse_args()
    try:
        datasource = parse_datasource(read_datasource_url())
        root = resolve_repository_root(args.repository_root)
        output_path, digest, client = export_schema(root, datasource)
        payload = {
            "result": "READY",
            "message": "schema 快照已通过只读客户端同步；未执行暂存或提交",
            "datasource": datasource.redacted_identity,
            "output_path": str(output_path),
            "sha256": digest,
            "client": client,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        exit_code = 0
    except SyncError as exc:
        payload = {"result": exc.result, "message": exc.message, **exc.facts}
        exit_code = HARD_BLOCK
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        payload = {
            "result": "INTERNAL_ERROR",
            "message": f"schema 同步无法稳定处理本地事实：{type(exc).__name__}",
        }
        exit_code = HARD_BLOCK
    render(payload, args.format)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
