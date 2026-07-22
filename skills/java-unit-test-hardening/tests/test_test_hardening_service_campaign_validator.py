import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SCRIPT = (
    SKILL_ROOT
    / "scripts/validate_service_campaign.py"
)


class ServiceCampaignValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.campaign = self.workspace / ".scratch/course-test-campaign"
        self.campaign.mkdir(parents=True)
        self.repository = self.workspace / "services/course"
        self.repository.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.repository, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repository,
            check=True,
        )
        (self.repository / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repository, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "fixture"], cwd=self.repository, check=True
        )
        self.repository_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repository,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_workflow_artifacts(self, workflow_id: str, status: str) -> str:
        relative = f".scratch/course-baseline-tests/{workflow_id}-tests"
        root = self.workspace / relative
        (root / "issues").mkdir(parents=True)
        (root / "PRD.md").write_text(
            f"campaign-status: {status}\n"
            "production-fix-policy: record-only-confirmed\n"
            "authorized-fix-tickets: none\n",
            encoding="utf-8",
        )
        (root / "PLAN.md").write_text(
            "production-fix-policy-snapshot: record-only-confirmed\n",
            encoding="utf-8",
        )
        (root / "REPORT.md").write_text(
            "行为矩阵已覆盖。\n",
            encoding="utf-8",
        )
        return relative

    def write_campaign(
        self,
        *,
        service_status: str = "in-progress",
        inventory_status: str = "partial",
        workflow_status: str = "pending",
        workflow_core: str = "yes",
        workflow_id: str = "course-video",
        mapped_workflow_id: str | None = None,
        scan_status: str = "partial",
        discovered: int = 0,
        mapped: int = 0,
        excluded: int = 0,
        artifact_dir: str = "none",
        service_report: bool = False,
        inventory_head: str | None = None,
    ) -> None:
        mapped_workflow_id = mapped_workflow_id or workflow_id
        inventory_head = inventory_head or self.repository_head
        (self.campaign / "BACKLOG.md").write_text(
            "# Course Test Hardening Campaign\n\n"
            f"service-campaign-status: {service_status}\n"
            f"core-inventory-status: {inventory_status}\n"
            "completion-policy: all-core-workflows\n"
            "service-baseline: 0123456789abcdef0123456789abcdef01234567\n\n"
            f"repository-root: {self.repository.resolve()}\n\n"
            "| workflow-id | module-id | core | priority | workflow | status | artifact-dir |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            f"| {workflow_id} | root | {workflow_core} | P0 | Course video | "
            f"{workflow_status} | {artifact_dir} |\n",
            encoding="utf-8",
        )
        (self.campaign / "CORE-FLOW-INVENTORY.md").write_text(
            "# Core Flow Inventory\n\n"
            f"inventory-status: {inventory_status}\n"
            f"inventory-head: {inventory_head}\n\n"
            "| module-id | module-path | scan-status | discovered-entry-count | mapped-entry-count | excluded-entry-count | evidence |\n"
            "| --- | --- | --- | ---: | ---: | ---: | --- |\n"
            f"| root | . | {scan_status} | {discovered} | {mapped} | {excluded} | CodeGraph |\n\n"
            "| flow-id | module-id | entry-symbols | workflow-id | core | evidence |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            f"| flow-course-video | root | CourseVideoController | {mapped_workflow_id} | yes | CodeGraph |\n",
            encoding="utf-8",
        )
        if service_report:
            residual = 1 if workflow_status == "residual-accepted" else 0
            complete = 1 if workflow_status == "complete" else 0
            (self.campaign / "SERVICE-REPORT.md").write_text(
                f"service-campaign-status: {service_status}\n"
                "core-workflows-total: 1\n"
                f"core-workflows-complete: {complete}\n"
                f"core-workflows-residual-accepted: {residual}\n",
                encoding="utf-8",
            )

    def run_validator(self) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--workspace-root",
                str(self.workspace),
                "--campaign-root",
                str(self.campaign),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(result.stdout) if result.stdout else {}
        return result, payload

    def test_template_style_inline_comments_parse_on_machine_lines(self) -> None:
        self.write_campaign(
            service_status="in-progress <!-- in-progress | complete | residual-accepted -->",
            inventory_status="partial <!-- partial | complete -->",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")
        self.assertEqual(payload["service_campaign_status"], "in-progress")

    def test_in_progress_campaign_accepts_partial_inventory_and_pending_core_work(self) -> None:
        self.write_campaign()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")
        self.assertEqual(payload["service_campaign_status"], "in-progress")
        self.assertFalse(payload["closure_ready"])

    def test_terminal_campaign_rejects_partial_inventory(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "complete")
        self.write_campaign(
            service_status="complete",
            inventory_status="partial",
            workflow_status="complete",
            artifact_dir=artifact,
            service_report=True,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("inventory-not-complete", self.violation_kinds(payload))

    def test_terminal_campaign_rejects_pending_core_workflow(self) -> None:
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            scan_status="complete",
            discovered=1,
            mapped=1,
            service_report=True,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("core-workflow-not-terminal", self.violation_kinds(payload))

    def test_complete_campaign_accepts_all_complete_core_workflows(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "complete")
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            workflow_status="complete",
            scan_status="complete",
            discovered=1,
            mapped=1,
            artifact_dir=artifact,
            service_report=True,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")
        self.assertTrue(payload["closure_ready"])

    def test_terminal_campaign_rejects_stale_inventory_head(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "complete")
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            workflow_status="complete",
            scan_status="complete",
            discovered=1,
            mapped=1,
            artifact_dir=artifact,
            service_report=True,
            inventory_head="f" * 40,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("inventory-head-stale", self.violation_kinds(payload))

    def test_terminal_campaign_uses_flow_evidence_without_class_size_gate(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "complete")
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            workflow_status="complete",
            scan_status="complete",
            discovered=1,
            mapped=1,
            artifact_dir=artifact,
            service_report=True,
        )
        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["closure_ready"])

    def test_residual_campaign_requires_residual_service_status(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "residual-accepted")
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            workflow_status="residual-accepted",
            scan_status="complete",
            discovered=1,
            mapped=1,
            artifact_dir=artifact,
            service_report=True,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("service-status-mismatch", self.violation_kinds(payload))

    def test_residual_campaign_accepts_terminal_core_workflows_and_report(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "residual-accepted")
        self.write_campaign(
            service_status="residual-accepted",
            inventory_status="complete",
            workflow_status="residual-accepted",
            scan_status="complete",
            discovered=1,
            mapped=1,
            artifact_dir=artifact,
            service_report=True,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["closure_ready"])

    def test_inventory_rejects_unknown_workflow_mapping(self) -> None:
        self.write_campaign(mapped_workflow_id="missing-workflow")

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("inventory-workflow-missing", self.violation_kinds(payload))

    def test_terminal_campaign_reconciles_module_entry_counts(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "complete")
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            workflow_status="complete",
            scan_status="complete",
            discovered=3,
            mapped=1,
            excluded=1,
            artifact_dir=artifact,
            service_report=True,
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("module-entry-count-mismatch", self.violation_kinds(payload))

    @staticmethod
    def violation_kinds(payload: dict) -> list[str]:
        return [violation["kind"] for violation in payload.get("violations", [])]


if __name__ == "__main__":
    unittest.main()


class ActiveBatchPointerClosureTest(ServiceCampaignValidatorTest):
    def test_terminal_campaign_rejects_dangling_active_batch_pointer(self) -> None:
        artifact = self.write_workflow_artifacts("course-video", "complete")
        self.write_campaign(
            service_status="complete",
            inventory_status="complete",
            workflow_status="complete",
            scan_status="complete",
            discovered=1,
            mapped=1,
            artifact_dir=artifact,
            service_report=True,
        )
        backlog = self.campaign / "BACKLOG.md"
        backlog.write_text(
            backlog.read_text(encoding="utf-8") + "\nactive-batch-status: running\n",
            encoding="utf-8",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        kinds = {item["kind"] for item in payload.get("violations", [])}
        self.assertIn("active-batch-dangling", kinds)
