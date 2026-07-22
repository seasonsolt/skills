import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SCRIPT = (
    SKILL_ROOT
    / "scripts/validate_portable_artifacts.py"
)


class PortableEvidenceSkillContractTest(unittest.TestCase):
    def test_skill_requires_portable_final_evidence_and_separate_schema_baseline(
        self,
    ) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for fragment in (
            "validate_portable_artifacts.py",
            "独立的 schema-baseline 维护",
            "同一目标仓库内已跟踪且干净",
            "禁止主机绝对路径",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, content)

        report = (SKILL_ROOT / "assets/templates/REPORT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Portable evidence validation", report)
        self.assertIn("repository-relative", report)
        self.assertNotIn("absolute or repository-relative", report)


class PortableEvidenceValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name) / "service"
        self.issue_dir = self.repository / "docs/tests/order-tests/issues"
        self.schema = self.repository / "db/schema/orders.sql"
        self.issue_dir.mkdir(parents=True)
        self.schema.parent.mkdir(parents=True)
        self.schema.write_text(
            "CREATE TABLE orders (id bigint NOT NULL);\n", encoding="utf-8"
        )
        self.run_git("init", "-q", "-b", "main")
        self.run_git("config", "user.name", "Test")
        self.run_git("config", "user.email", "test@example.com")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repository,
            check=True,
            capture_output=True,
            text=True,
        )

    def commit_all(self) -> None:
        self.run_git("add", "docs/tests", "db/schema")
        self.run_git("commit", "-qm", "baseline")

    def write_issue(self, content: str) -> None:
        (self.issue_dir / "01.md").write_text(content, encoding="utf-8")

    def run_validator(self) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--repository-root",
                str(self.repository),
                "--docs-root",
                "docs/tests",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result, json.loads(result.stdout)

    def test_accepts_tracked_clean_repository_schema_with_document_relative_link(
        self,
    ) -> None:
        digest = hashlib.sha256(self.schema.read_bytes()).hexdigest()
        self.write_issue(
            "Schema："
            "[db/schema/orders.sql](../../../../db/schema/orders.sql)，"
            f"SHA-256 `{digest}`。\n"
        )
        self.commit_all()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")
        self.assertEqual(payload["schema_sources"], ["db/schema/orders.sql"])

    def test_rejects_absolute_local_path(self) -> None:
        self.write_issue(
            "Schema：`/Users/example/work/services/order/db/schema/orders.sql`。\n"
        )
        self.commit_all()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(
            "absolute-local-path",
            {violation["kind"] for violation in payload["violations"]},
        )

    def test_rejects_absolute_local_toolchain_path(self) -> None:
        self.write_issue(
            "复跑：`JAVA_HOME=/opt/homebrew/opt/openjdk@21 mvn test`。\n"
        )
        self.commit_all()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(
            "absolute-local-path",
            {violation["kind"] for violation in payload["violations"]},
        )

    def test_rejects_schema_link_that_escapes_the_repository(self) -> None:
        self.write_issue(
            "Schema：[orders](../../../../../../course/db/schema/orders.sql)。\n"
        )
        self.commit_all()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(
            "schema-path-outside-repository",
            {violation["kind"] for violation in payload["violations"]},
        )

    def test_rejects_untracked_schema(self) -> None:
        self.write_issue("Schema：`db/schema/orders.sql`。\n")
        self.run_git("add", "docs/tests")
        self.run_git("commit", "-qm", "docs only")

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(
            "schema-untracked",
            {violation["kind"] for violation in payload["violations"]},
        )

    def test_rejects_dirty_schema(self) -> None:
        self.write_issue("Schema：`db/schema/orders.sql`。\n")
        self.commit_all()
        self.schema.write_text(
            "CREATE TABLE orders (id bigint NOT NULL, code varchar(32));\n",
            encoding="utf-8",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(
            "schema-dirty",
            {violation["kind"] for violation in payload["violations"]},
        )

    def test_rejects_declared_schema_hash_mismatch(self) -> None:
        self.write_issue(
            "Schema：`db/schema/orders.sql`，"
            f"SHA-256 `{'0' * 64}`。\n"
        )
        self.commit_all()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(
            "schema-hash-mismatch",
            {violation["kind"] for violation in payload["violations"]},
        )

    def test_schema_readme_link_is_not_mistaken_for_a_sql_snapshot(self) -> None:
        self.write_issue("说明：[db/schema/README.md](../../../../db/schema/README.md)。\n")
        self.run_git("add", "docs/tests")
        self.run_git("commit", "-qm", "docs")

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["schema_sources"], [])


if __name__ == "__main__":
    unittest.main()
