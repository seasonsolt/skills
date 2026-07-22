import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SCRIPT = (
    SKILL_ROOT
    / "scripts/sync_schema.py"
)


class TestHardeningSchemaSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "service"
        self.root.mkdir()
        (self.root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        subprocess.run(
            ["git", "init", "-b", "master"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.root, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(["git", "add", "pom.xml"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        self.bin = Path(self.temporary_directory.name) / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def install_client(self, name: str, body: str) -> Path:
        executable = self.bin / name
        executable.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def run_sync(self, url: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = f"{self.bin}:{environment.get('PATH', '')}"
        environment["SYNC_TEST_LOG"] = str(
            Path(self.temporary_directory.name) / "client.log"
        )
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--repository-root",
                str(self.root),
                "--format",
                "json",
            ],
            input=url + "\n",
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    def test_mysql_jdbc_url_is_read_from_stdin_and_secret_is_not_logged(self) -> None:
        self.install_client(
            "mysqldump",
            textwrap.dedent(
                """
                printf '%s\n' "$*" > "$SYNC_TEST_LOG"
                printf 'password=%s\n' "${MYSQL_PWD:-}" >> "$SYNC_TEST_LOG"
                printf 'CREATE TABLE `orders` (`id` bigint NOT NULL);\n'
                """
            ),
        )
        secret = "top-secret"

        result = self.run_sync(
            f"jdbc:mysql://reader:{secret}@db.internal:3307/orders?sslMode=REQUIRED"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["result"], "READY")
        self.assertEqual(payload["datasource"], "mysql://db.internal:3307/orders")
        self.assertIn("generated_at", payload)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertEqual(
            (self.root / "db/schema/orders.sql").read_text(encoding="utf-8"),
            "CREATE TABLE `orders` (`id` bigint NOT NULL);\n",
        )
        log = (Path(self.temporary_directory.name) / "client.log").read_text(
            encoding="utf-8"
        )
        self.assertIn("--no-data", log)
        self.assertIn("--ssl-mode=REQUIRED", log)
        self.assertNotIn(secret, log.splitlines()[0])
        self.assertIn(f"password={secret}", log)

    def test_postgresql_url_uses_schema_only_dump(self) -> None:
        self.install_client(
            "pg_dump",
            textwrap.dedent(
                """
                printf '%s\n' "$*" > "$SYNC_TEST_LOG"
                printf 'password=%s\n' "${PGPASSWORD:-}" >> "$SYNC_TEST_LOG"
                printf 'CREATE TABLE public.invoice (id bigint NOT NULL);\n'
                """
            ),
        )

        result = self.run_sync(
            "jdbc:postgresql://reader:pg-secret@pg.internal/billing?sslmode=require"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["datasource"], "postgresql://pg.internal:5432/billing")
        log = (Path(self.temporary_directory.name) / "client.log").read_text(
            encoding="utf-8"
        )
        self.assertIn("--schema-only", log)
        self.assertIn("password=pg-secret", log)

    def test_dirty_snapshot_is_never_overwritten(self) -> None:
        snapshot = self.root / "db/schema/orders.sql"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text("original\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "db/schema/orders.sql"], cwd=self.root, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "schema"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        snapshot.write_text("local change\n", encoding="utf-8")
        self.install_client("mysqldump", "printf 'should not run\n'\n")

        result = self.run_sync("mysql://reader:secret@db.internal/orders")

        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["result"], "SNAPSHOT_DIRTY")
        self.assertEqual(snapshot.read_text(encoding="utf-8"), "local change\n")
        self.assertNotIn("secret", result.stdout + result.stderr)

    def test_unsupported_url_does_not_echo_credentials(self) -> None:
        result = self.run_sync("jdbc:oracle://reader:private@db.internal/orders")

        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["result"], "UNSUPPORTED_DATASOURCE")
        self.assertNotIn("private", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()


class DatasourceInjectionGuardTest(unittest.TestCase):
    def test_leading_hyphen_database_name_is_rejected(self) -> None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("sync_schema", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        # Python 3.14 延迟注解解析要求模块在 sys.modules 中可查。
        sys.modules["sync_schema"] = module
        spec.loader.exec_module(module)

        with self.assertRaises(module.SyncError):
            module.parse_datasource("jdbc:mysql://db-host:3306/-ops?user=reader")
