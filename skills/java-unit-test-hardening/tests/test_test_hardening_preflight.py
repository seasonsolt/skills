import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts/preflight.py"


class StandalonePreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "order-service"
        self.repository.mkdir()
        self.write_root_pom()
        self.run_git("init", "-q", "-b", "main")
        self.run_git("config", "user.name", "Test")
        self.run_git("config", "user.email", "test@example.com")
        self.commit_all("baseline")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_root_pom(self, modules: tuple[str, ...] = ()) -> None:
        module_xml = "".join(f"<module>{module}</module>" for module in modules)
        modules_xml = f"<modules>{module_xml}</modules>" if modules else ""
        (self.repository / "pom.xml").write_text(
            textwrap.dedent(
                f"""
                <project xmlns="http://maven.apache.org/POM/4.0.0">
                  <modelVersion>4.0.0</modelVersion>
                  <groupId>example</groupId>
                  <artifactId>order-service</artifactId>
                  <version>1</version>
                  {modules_xml}
                </project>
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def run_git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            check=True,
            capture_output=True,
            text=True,
        )

    def commit_all(self, message: str) -> None:
        self.run_git("add", "-A")
        self.run_git("commit", "-qm", message)

    def run_preflight(
        self,
        *extra: str,
        repository: Path | None = None,
        campaign_workspace: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repository-root",
                str(repository or self.repository),
                "--campaign-workspace",
                str(campaign_workspace or self.root),
                *extra,
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return result, json.loads(result.stdout)

    def test_clean_single_module_repository_is_ready(self) -> None:
        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "READY")
        self.assertEqual(payload["service"], "order-service")
        self.assertEqual(payload["repository_root"], str(self.repository.resolve()))
        self.assertEqual(payload["campaign_workspace"], str(self.root.resolve()))
        self.assertEqual(
            payload["campaign_root"],
            str((self.root / ".scratch/order-service-test-campaign").resolve()),
        )
        self.assertEqual(payload["modules"], [])
        self.assertEqual(payload["target_scope"], "service-campaign")
        self.assertTrue(payload["repository_identity_verified"])

    def test_preflight_is_read_only(self) -> None:
        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 0, payload)
        self.assertFalse((self.root / ".scratch").exists())
        status = self.run_git("status", "--porcelain").stdout
        self.assertEqual(status, "")

    def test_origin_credentials_are_not_emitted(self) -> None:
        secret = "super-secret"
        self.run_git(
            "remote",
            "add",
            "origin",
            f"https://reader:{secret}@example.com/acme/order-service.git?token=hidden#x",
        )

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            payload["origin_url"], "https://example.com/acme/order-service.git"
        )
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn("token=hidden", result.stdout + result.stderr)

    def test_repository_argument_must_be_exact_git_root(self) -> None:
        child = self.repository / "src"
        child.mkdir()

        result, payload = self.run_preflight(
            "--service-campaign", repository=child
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["result"], "REPOSITORY_NOT_ROOT")
        self.assertEqual(payload["repository_root"], str(self.repository.resolve()))

    def test_missing_root_pom_is_rejected(self) -> None:
        (self.repository / "pom.xml").unlink()
        self.run_git("add", "pom.xml")
        self.run_git("commit", "-qm", "remove pom")

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["result"], "UNSUPPORTED_PROJECT")

    def test_untracked_file_blocks_entry(self) -> None:
        (self.repository / "notes.txt").write_text("mine\n", encoding="utf-8")

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["result"], "WORKTREE_NOT_CLEAN")
        self.assertEqual(payload["untracked_files"], ["notes.txt"])

    def test_tracked_change_blocks_entry(self) -> None:
        (self.repository / "pom.xml").write_text("<project/>\n", encoding="utf-8")

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["result"], "WORKTREE_NOT_CLEAN")
        self.assertEqual(payload["tracked_changes"], ["pom.xml"])

    def test_git_operation_marker_blocks_entry(self) -> None:
        marker = Path(self.run_git("rev-parse", "--git-path", "MERGE_HEAD").stdout.strip())
        if not marker.is_absolute():
            marker = self.repository / marker
        marker.write_text("0" * 40 + "\n", encoding="ascii")

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["result"], "GIT_OPERATION_IN_PROGRESS")
        self.assertIn("MERGE_HEAD", payload["git_operation_markers"])

    def test_campaign_workspace_must_be_outside_repository(self) -> None:
        inside = self.repository / "campaign"
        inside.mkdir()

        result, payload = self.run_preflight(
            "--service-campaign", campaign_workspace=inside
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(
            payload["result"], "CAMPAIGN_WORKSPACE_INSIDE_REPOSITORY"
        )

    def test_invalid_repository_name_requires_explicit_service_id(self) -> None:
        renamed = self.root / "order service"
        self.repository.rename(renamed)
        self.repository = renamed

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["result"], "SERVICE_ID_REQUIRED")

        ready, ready_payload = self.run_preflight(
            "--service-campaign", "--service-id", "order-service"
        )
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual(ready_payload["service"], "order-service")

    def make_modules(self, modules: tuple[str, ...] = ("api", "service")) -> None:
        self.write_root_pom(modules)
        for module in modules:
            module_root = self.repository / module
            module_root.mkdir(parents=True)
            (module_root / "pom.xml").write_text(
                "<project><modelVersion>4.0.0</modelVersion></project>\n",
                encoding="utf-8",
            )
        self.commit_all("add modules")

    def test_service_campaign_discovers_all_modules(self) -> None:
        self.make_modules()

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["modules"], ["api", "service"])

    def test_module_mode_requires_selection_for_multi_module_repository(self) -> None:
        self.make_modules()

        result, payload = self.run_preflight()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["result"], "MODULE_SELECTION_REQUIRED")
        self.assertEqual(payload["modules"], ["api", "service"])

        ready, ready_payload = self.run_preflight("--module", "api")
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual(ready_payload["module"], "api")

    def test_unknown_module_is_rejected(self) -> None:
        self.make_modules(("api",))

        result, payload = self.run_preflight("--module", "missing")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["result"], "MODULE_INVALID")

    def test_service_campaign_cannot_also_bind_module(self) -> None:
        self.make_modules(("api",))

        result, payload = self.run_preflight(
            "--service-campaign", "--module", "api"
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["result"], "MODULE_SCOPE_CONFLICT")

    def test_module_path_cannot_escape_repository(self) -> None:
        self.write_root_pom(("../outside",))
        self.commit_all("bad module")

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["result"], "MAVEN_INVALID")

    def test_existing_backlog_is_reported_as_resume_candidate(self) -> None:
        campaign = self.root / ".scratch/order-service-test-campaign"
        campaign.mkdir(parents=True)
        (campaign / "BACKLOG.md").write_text(
            "| workflow-id | status | branch |\n"
            "| --- | --- | --- |\n"
            "| checkout | in-progress | main |\n",
            encoding="utf-8",
        )

        result, payload = self.run_preflight("--service-campaign")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["resume_candidate"])


if __name__ == "__main__":
    unittest.main()
