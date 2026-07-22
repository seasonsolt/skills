import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SCRIPT = SKILL_ROOT / "scripts/batch_run.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import batch_run as batch_module  # noqa: E402


class BatchRunStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name) / "workspace"
        self.repository = self.workspace / "services/course"
        self.repository.mkdir(parents=True)
        (self.repository / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        (self.repository / ".gitignore").write_text("target/\n", encoding="utf-8")
        subprocess.run(
            ["git", "init", "-b", "ut-batch"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.repository, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repository,
            check=True,
        )
        subprocess.run(
            ["git", "add", "pom.xml", ".gitignore"],
            cwd=self.repository,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        self.baseline = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.campaign_root = self.workspace / ".scratch/course-test-campaign"
        self.batch_dir = self.campaign_root / "batches/course-20260715-wave-01"
        self.batch_dir.mkdir(parents=True)
        self.run_file = self.batch_dir / "BATCH-RUN.json"
        self.inventory = self.campaign_root / "CORE-FLOW-INVENTORY.md"
        self.inventory.write_text("inventory-status: complete\n", encoding="utf-8")
        self.clock = datetime(2026, 7, 15, 2, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def timestamp(self) -> str:
        self.clock += timedelta(minutes=1)
        return self.clock.isoformat()

    def manifest(self) -> dict:
        inventory_hash = hashlib.sha256(self.inventory.read_bytes()).hexdigest()
        return {
            "version": 2,
            "batch_id": "course-20260715-wave-01",
            "service": "course",
            "workspace_root": str(self.workspace),
            "repository_root": str(self.repository),
            "branch": "ut-batch",
            "baseline": self.baseline,
            "inventory_path": str(self.inventory),
            "inventory_sha256": inventory_hash,
            "production_fix_policy": "record-only-confirmed",
            "execution_mode": "sequential",
            "selection": {
                "approved_by": "workspace-user",
                "approved_at": "2026-07-15T10:00:00+08:00",
                "decision_source": "使用人在一次交互中选择两个 workflow。",
            },
            "agent_policy": {
                "coordinator": "root",
                "initial_writer": "root",
                "read_only_subagents": True,
            },
            "workflows": [
                {
                    "workflow_id": "live-reward",
                    "module_id": "root",
                    "order": 1,
                    "dependencies": [],
                    "source_status": "pending",
                    "artifact_dir": ".scratch/course-baseline-tests/live-reward-tests",
                    "docs_path": "docs/tests/live-reward-tests",
                    "test_build_files": [],
                    "integration_lane": "required",
                },
                {
                    "workflow_id": "live-room",
                    "module_id": "root",
                    "order": 2,
                    "dependencies": ["live-reward"],
                    "source_status": "pending",
                    "artifact_dir": ".scratch/course-baseline-tests/live-room-tests",
                    "docs_path": "docs/tests/live-room-tests",
                    "test_build_files": [],
                    "integration_lane": "not-applicable",
                },
            ],
            "repository_baseline": None,
            "transitions": [],
        }

    def enable_modules(self) -> None:
        """Turn the fixture repository into a two-module Maven reactor and
        advance the recorded baseline to the commit that contains it."""
        (self.repository / "pom.xml").write_text(
            "<project><modules>"
            "<module>mod-a</module><module>mod-b</module>"
            "</modules></project>\n",
            encoding="utf-8",
        )
        for module in ("mod-a", "mod-b"):
            module_dir = self.repository / module
            module_dir.mkdir()
            (module_dir / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "pom.xml", "mod-a/pom.xml", "mod-b/pom.xml"],
            cwd=self.repository,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "modules"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        self.baseline = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def parallel_manifest(self, *, max_concurrent: int = 2) -> dict:
        manifest = self.manifest()
        manifest["execution_mode"] = "parallel"
        manifest["max_concurrent_workflows"] = max_concurrent
        for workflow, module in zip(manifest["workflows"], ("mod-a", "mod-b")):
            workflow_id = workflow["workflow_id"]
            workflow["module_id"] = module
            workflow["dependencies"] = []
            workflow["worktree"] = (
                f".scratch/course-test-campaign/worktrees/{workflow_id}"
            )
            workflow["branch"] = f"ut-parallel-{workflow_id}"
            workflow["writer"] = f"writer-{workflow_id}"
        return manifest

    def add_worktree(self, workflow: dict) -> Path:
        path = self.workspace / workflow["worktree"]
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                str(path),
                "-b",
                workflow["branch"],
                self.baseline,
            ],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )
        return path

    def setup_parallel(
        self,
        *,
        max_concurrent: int = 2,
        mutate=None,
        worktrees: bool = True,
    ) -> dict:
        self.enable_modules()
        manifest = self.parallel_manifest(max_concurrent=max_concurrent)
        if mutate is not None:
            mutate(manifest)
        self.write_manifest(manifest)
        if worktrees:
            for workflow in manifest["workflows"]:
                self.add_worktree(workflow)
        self.seal()
        return manifest

    def write_manifest(self, payload: dict | None = None) -> None:
        self.run_file.write_text(
            json.dumps(payload or self.manifest(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def raw_state(self) -> dict:
        return json.loads(self.run_file.read_text(encoding="utf-8"))

    def state(self) -> dict:
        payload = self.raw_state()
        if not payload.get("selection_contract_sha256"):
            return payload
        derived, violations = batch_module.replay_journal(payload)
        self.assertEqual(violations, [])
        view = json.loads(json.dumps(payload))
        view.update(derived)
        for workflow in view["workflows"]:
            workflow.update(derived["workflow_statuses"][workflow["workflow_id"]])
        return view

    def run_script(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            ["python3", str(SCRIPT), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(result.stdout) if result.stdout else {}
        return result, payload

    def seal(self) -> dict:
        result, payload = self.run_script(
            "seal", "--run-file", str(self.run_file), "--format", "json"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return payload

    def audit(
        self, workflow: str, *, actor: str = "root"
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.run_script(
            "audit",
            "--run-file",
            str(self.run_file),
            "--workflow",
            workflow,
            "--actor",
            actor,
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        )

    def transition(
        self,
        workflow: str,
        target: str,
        *,
        evidence: str | None = None,
        evidence_manifest: Path | None = None,
        actor: str = "root",
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [
            "transition",
            "--run-file",
            str(self.run_file),
            "--workflow",
            workflow,
            "--to",
            target,
            "--actor",
            actor,
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        ]
        if evidence is not None:
            arguments.extend(("--evidence", evidence))
        if evidence_manifest is not None:
            arguments.extend(("--evidence-manifest", str(evidence_manifest)))
        return self.run_script(*arguments)

    def advance(
        self,
        workflow: str,
        target: str,
        *,
        evidence: str | None = None,
        evidence_manifest: Path | None = None,
        actor: str = "root",
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [
            "advance",
            "--run-file",
            str(self.run_file),
            "--workflow",
            workflow,
            "--to",
            target,
            "--actor",
            actor,
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        ]
        if evidence is not None:
            arguments.extend(("--evidence", evidence))
        if evidence_manifest is not None:
            arguments.extend(("--evidence-manifest", str(evidence_manifest)))
        return self.run_script(*arguments)

    def start(self, workflow: str, *, actor: str = "root") -> None:
        started, payload = self.advance(
            workflow, "in-progress", evidence="PLAN.md#red", actor=actor
        )
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertEqual(payload["current_workflow_id"], workflow)

    def test_advance_audits_and_starts_workflow_atomically(self) -> None:
        self.write_manifest()
        self.seal()

        started, payload = self.advance(
            "live-reward", "in-progress", evidence="PLAN.md#red"
        )

        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertEqual(payload["current_workflow_id"], "live-reward")
        self.assertEqual(self.state()["transitions"][-2]["event"], "boundary-audit")
        self.assertEqual(self.state()["transitions"][-1]["event"], "workflow-transition")
        self.assertEqual(
            self.state()["transitions"][-2]["audit_fingerprint"],
            self.state()["transitions"][-1]["audit_fingerprint"],
        )

    def test_advance_rolls_back_audit_when_transition_is_invalid(self) -> None:
        self.write_manifest()
        self.seal()

        rejected, payload = self.advance("live-reward", "in-progress")

        self.assertEqual(rejected.returncode, 2)
        self.assertIn("start-evidence-required", str(payload["violations"]))
        self.assertEqual(self.state()["revision"], 0)
        self.assertEqual(self.raw_state()["transitions"], [])

    def test_audit_event_stores_count_not_full_changed_paths(self) -> None:
        # 全量 changed_paths 已折叠进 audit_fingerprint；逐事件内嵌
        # 全量路径+哈希会让台账随进度膨胀（实测 17 次审计 = 413KB）。
        self.write_manifest()
        self.seal()
        audited, _ = self.audit("live-reward")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

        event = self.state()["transitions"][-1]

        self.assertEqual(event["event"], "boundary-audit")
        self.assertIsInstance(event["changed_path_count"], int)
        self.assertNotIn("changed_paths", event)
        # 只存计数不影响 audit→transition 的指纹耦合。
        started, payload = self.transition(
            "live-reward", "in-progress", evidence="PLAN.md#red"
        )
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertEqual(payload["current_workflow_id"], "live-reward")

    def create_terminal_evidence(
        self,
        workflow_id: str,
        *,
        status: str = "complete",
        actor: str = "root",
        ticket_id: str = "01",
        ticket_regression: str = "expectedBehavior",
        xml_regression: str = "expectedBehavior",
    ) -> tuple[Path, str]:
        workflow = next(
            item for item in self.state()["workflows"] if item["workflow_id"] == workflow_id
        )
        campaign = self.workspace / workflow["artifact_dir"]
        (campaign / "issues").mkdir(parents=True, exist_ok=True)
        (campaign / "PRD.md").write_text(
            f"campaign-status: {status}\n"
            "ticket-evidence-version: 1\n"
            "production-fix-policy: record-only-confirmed\n"
            "authorized-fix-tickets: none\n",
            encoding="utf-8",
        )
        (campaign / "PLAN.md").write_text(
            "production-fix-policy-snapshot: record-only-confirmed\n",
            encoding="utf-8",
        )
        (campaign / "REPORT.md").write_text(
            "测试行为矩阵已全部覆盖。\n",
            encoding="utf-8",
        )
        (campaign / "BEHAVIOR-MATRIX.md").write_text(
            f"# {workflow_id}\n", encoding="utf-8"
        )
        issue = campaign / f"issues/{ticket_id}-defect.md"
        issue.write_text(
            "# 缺陷票据\n\n"
            "status: recorded\n"
            "finding-type: defect\n"
            "verification: confirmed\n"
            "severity: medium\n"
            "priority: P1\n"
            "characterization-tests: `BehaviorTest#currentBehavior`\n"
            f"regression-tests: `BehaviorTest#{ticket_regression}`\n\n"
            "Production fix is out of scope for the current campaign.\n",
            encoding="utf-8",
        )

        # Worktree-bound workflows land their docs/tests copies inside their
        # own linked worktree; sequential workflows keep the main repository.
        docs_root = (
            self.workspace / workflow["worktree"]
            if workflow.get("worktree")
            else self.repository
        )
        docs = docs_root / workflow["docs_path"]
        (docs / "issues").mkdir(parents=True, exist_ok=True)
        shutil.copy2(campaign / "REPORT.md", docs / "REPORT.md")
        shutil.copy2(campaign / "BEHAVIOR-MATRIX.md", docs / "BEHAVIOR-MATRIX.md")
        shutil.copy2(issue, docs / f"issues/{ticket_id}-defect.md")

        evidence_dir = campaign / "evidence"
        evidence_dir.mkdir()
        unit_xml = evidence_dir / "unit.xml"
        unit_xml.write_text(
            '<testsuite tests="2" failures="0" errors="0" skipped="1">'
            '<testcase classname="example.BehaviorTest" name="currentBehavior"/>'
            f'<testcase classname="example.BehaviorTest" name="{xml_regression}">'
            f'<skipped message="issues/{ticket_id} - production fix is out of scope for this campaign"/>'
            "</testcase></testsuite>\n",
            encoding="utf-8",
        )
        unit_runs = [self.result_run("unit-1", [unit_xml])]
        integration_runs: list[dict] = []
        if workflow["integration_lane"] == "required":
            for index in range(1, 2):
                report = evidence_dir / f"integration-{index}.xml"
                report.write_text(
                    '<testsuite tests="1" failures="0" errors="0" skipped="0"/>\n',
                    encoding="utf-8",
                )
                integration_runs.append(
                    self.result_run(f"integration-{index}", [report])
                )

        copied = []
        for name in (
            "REPORT.md",
            "BEHAVIOR-MATRIX.md",
            f"issues/{ticket_id}-defect.md",
        ):
            source = campaign / name
            target = docs / name
            copied.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }
            )
        manifest = {
            "version": 1,
            "batch_id": self.state()["batch_id"],
            "service": "course",
            "workflow_id": workflow_id,
            "campaign_dir": str(campaign),
            "docs_path": workflow["docs_path"],
            "production_fix_policy": "record-only-confirmed",
            "unit_test_runs": unit_runs,
            "integration_test_runs": integration_runs,
            "copied_artifacts": copied,
        }
        evidence_manifest = campaign / "WORKFLOW-EVIDENCE.json"
        evidence_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return evidence_manifest, ""

    @staticmethod
    def result_run(run_id: str, paths: list[Path]) -> dict:
        return {
            "run_id": run_id,
            "report_files": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in paths
            ],
        }

    def complete(self, workflow: str, *, actor: str = "root") -> None:
        evidence, _ = self.create_terminal_evidence(workflow, actor=actor)
        result, payload = self.advance(
            workflow, "complete", evidence_manifest=evidence, actor=actor
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(payload["batch_status"], {"running", "complete"})

    def test_seal_and_validate_confirmed_batch(self) -> None:
        self.write_manifest()

        sealed = self.seal()
        result, payload = self.run_script(
            "validate", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["result"], "VALID")
        self.assertEqual(payload["selected_workflows"], 2)
        self.assertEqual(sealed["writer"], "root")
        self.assertEqual(sealed["revision"], 0)
        self.assertEqual(self.state()["writer"], "root")
        self.assertEqual(self.state()["revision"], len(self.state()["transitions"]))
        self.assertIsInstance(self.state()["repository_baseline"], dict)
        for key in ("writer", "status", "current_workflow_id", "pause", "revision", "last_boundary_audit"):
            self.assertNotIn(key, self.raw_state())
        self.assertNotIn("status", self.raw_state()["workflows"][0])
        self.assertNotIn("evidence", self.raw_state()["workflows"][0])

    def test_seal_derives_fixed_policy_instead_of_storing_duplicate_fields(self) -> None:
        manifest = self.manifest()
        self.write_manifest(manifest)

        sealed = self.seal()

        for key in ("goal_objective", "goal_contract", "batch_grants"):
            self.assertNotIn(key, self.state())
        self.assertNotIn("one_repository_writer", self.state()["agent_policy"])
        self.assertEqual(sealed["selected_workflows"], 2)

    def test_seal_rejects_missing_or_empty_artifact_dir(self) -> None:
        manifest = self.manifest()
        del manifest["workflows"][0]["artifact_dir"]
        manifest["workflows"][1]["artifact_dir"] = ""
        self.write_manifest(manifest)

        result, payload = self.run_script(
            "seal", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("invalid-artifact-dir", self.violation_kinds(payload))

    def test_seal_rejects_module_id_missing_from_live_reactor(self) -> None:
        manifest = self.manifest()
        manifest["workflows"][0]["module_id"] = "ghost-module"
        self.write_manifest(manifest)

        result, payload = self.run_script(
            "seal", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("workflow-module-unknown", self.violation_kinds(payload))

    def mutate_run_file(self, mutate) -> None:
        payload = self.raw_state()
        mutate(payload)
        self.run_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_sealed_contract_rejects_silently_appended_workflow(self) -> None:
        self.write_manifest()
        self.seal()

        def append_workflow(payload: dict) -> None:
            extra = dict(payload["workflows"][1])
            extra["workflow_id"] = "live-extra"
            extra["order"] = 3
            extra["dependencies"] = []
            extra["artifact_dir"] = ".scratch/course-baseline-tests/live-extra-tests"
            extra["docs_path"] = "docs/tests/live-extra-tests"
            payload["workflows"].append(extra)

        self.mutate_run_file(append_workflow)
        result, payload = self.run_script(
            "validate", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("selection-contract-drift", self.violation_kinds(payload))

    def test_seal_is_once_only(self) -> None:
        self.write_manifest()
        self.seal()

        result, payload = self.run_script(
            "seal", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("already-sealed", self.violation_kinds(payload))

    def test_batch_rejects_multiple_or_inactive_writers(self) -> None:
        manifest = self.manifest()
        manifest["agent_policy"]["initial_writer"] = ["root", "writer-2"]
        self.write_manifest(manifest)

        result, payload = self.run_script(
            "seal", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("invalid-writer-policy", self.violation_kinds(payload))

    def test_existing_in_progress_workflow_is_first_but_runtime_starts_pending(self) -> None:
        manifest = self.manifest()
        manifest["workflows"][0]["source_status"] = "in-progress"
        self.write_manifest(manifest)

        self.seal()

        self.assertEqual(self.state()["workflows"][0]["source_status"], "in-progress")
        self.assertEqual(self.state()["workflows"][0]["status"], "pending")
        self.start("live-reward")

    def test_terminal_backlog_workflow_cannot_be_selected_again(self) -> None:
        manifest = self.manifest()
        manifest["workflows"][0]["source_status"] = "complete"
        self.write_manifest(manifest)

        result, payload = self.run_script(
            "seal", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("invalid-source-status", self.violation_kinds(payload))

    def test_transition_is_dependency_ordered_and_audit_gated(self) -> None:
        self.write_manifest()
        self.seal()

        audited, _ = self.audit("live-room")
        self.assertEqual(audited.returncode, 0, audited.stderr)
        rejected, payload = self.transition(
            "live-room", "in-progress", evidence="PLAN.md#red"
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("workflow-out-of-order", self.violation_kinds(payload))

        self.start("live-reward")
        self.complete("live-reward")
        self.start("live-room")

        state = self.state()
        self.assertEqual(state["current_workflow_id"], "live-room")
        self.assertEqual(state["workflows"][0]["status"], "complete")
        self.assertEqual(state["workflows"][1]["status"], "in-progress")

    def test_batch_completes_only_after_every_selected_workflow_is_terminal(self) -> None:
        self.write_manifest()
        self.seal()
        self.start("live-reward")
        self.complete("live-reward")
        self.assertEqual(self.state()["status"], "running")

        self.start("live-room")
        self.complete("live-room")

        self.assertEqual(self.state()["status"], "complete")
        self.assertEqual(self.state()["current_workflow_id"], None)

    def test_reordered_journal_event_is_rejected(self) -> None:
        # The tamper-evident hash chain is gone, but the append-only journal is
        # still replayed on read and its revision sequence is validated, so a
        # structural edit (a reordered or renumbered event) fails validation.
        self.write_manifest()
        self.seal()
        self.start("live-reward")
        manifest = self.raw_state()
        manifest["transitions"][0]["revision"] = 99
        self.write_manifest(manifest)

        result, payload = self.run_script(
            "validate", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("journal-sequence-mismatch", self.violation_kinds(payload))

    def test_expected_revision_conflict_is_rejected(self) -> None:
        # Optimistic CAS across invocations: a stale --expected-revision (as a
        # loser of a concurrent race would present) is rejected before any
        # journal append.
        self.write_manifest()
        self.seal()

        result, payload = self.run_script(
            "audit",
            "--run-file",
            str(self.run_file),
            "--workflow",
            "live-reward",
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            "7",
            "--format",
            "json",
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("revision-mismatch", self.violation_kinds(payload))
        self.assertEqual(self.state()["revision"], 0)

    def test_only_active_writer_can_advance_batch(self) -> None:
        self.write_manifest()
        self.seal()

        result, payload = self.audit("live-reward", actor="parallel-reviewer")

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("writer-lease-mismatch", self.violation_kinds(payload))
        self.assertEqual(self.state()["status"], "confirmed")

    def test_pause_then_reaudit_and_resume(self) -> None:
        self.write_manifest()
        self.seal()
        self.start("live-reward")

        paused, paused_payload = self.run_script(
            "pause",
            "--run-file",
            str(self.run_file),
            "--reason",
            "Required Docker runtime is unavailable.",
            "--resume-command",
            "mvn -Pintegration-tests verify",
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        )
        self.assertEqual(paused.returncode, 0, paused.stdout + paused.stderr)
        self.assertEqual(paused_payload["batch_status"], "paused")

        audited, _ = self.audit("live-reward")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)
        resumed, resumed_payload = self.run_script(
            "resume",
            "--run-file",
            str(self.run_file),
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        )

        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertEqual(resumed_payload["batch_status"], "running")
        self.assertEqual(resumed_payload["current_workflow_id"], "live-reward")
        self.assertEqual(self.state()["revision"], len(self.state()["transitions"]))

    def test_paused_batch_cannot_advance_until_explicit_resume(self) -> None:
        self.write_manifest()
        self.seal()
        paused, _ = self.run_script(
            "pause",
            "--run-file",
            str(self.run_file),
            "--reason",
            "Entry facts require review.",
            "--resume-command",
            "python3 preflight.py --service course --service-campaign",
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            "0",
            "--format",
            "json",
        )
        self.assertEqual(paused.returncode, 0, paused.stderr)
        audited, _ = self.audit("live-reward")
        self.assertEqual(audited.returncode, 0, audited.stderr)

        result, payload = self.transition(
            "live-reward", "in-progress", evidence="PLAN.md#red"
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("invalid-batch-transition", self.violation_kinds(payload))

    def test_terminal_transition_rejects_arbitrary_evidence_string(self) -> None:
        self.write_manifest()
        self.seal()
        self.start("live-reward")
        audited, _ = self.audit("live-reward")
        self.assertEqual(audited.returncode, 0, audited.stderr)

        result, payload = self.transition(
            "live-reward", "complete", evidence="REPORT.md"
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("terminal-evidence-required", self.violation_kinds(payload))

    def test_terminal_transition_rejects_ticket_test_missing_from_runner_xml(self) -> None:
        self.write_manifest()
        self.seal()
        self.start("live-reward")
        evidence, _ = self.create_terminal_evidence(
            "live-reward",
            ticket_regression="expectedBehavior",
            xml_regression="differentExpectedBehavior",
        )

        result, payload = self.advance(
            "live-reward", "complete", evidence_manifest=evidence
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("ticket-test-reference-missing", self.violation_kinds(payload))

    def test_terminal_transition_accepts_alphanumeric_ticket_id(self) -> None:
        self.write_manifest()
        self.seal()
        self.start("live-reward")
        evidence, _ = self.create_terminal_evidence(
            "live-reward", ticket_id="PSP-001"
        )

        result, payload = self.advance(
            "live-reward", "complete", evidence_manifest=evidence
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(payload["batch_status"], {"running", "complete"})

    def test_residual_acceptance_requires_separate_user_receipt(self) -> None:
        self.write_manifest()
        self.seal()
        self.start("live-reward")
        evidence, _ = self.create_terminal_evidence(
            "live-reward", status="residual-accepted"
        )

        rejected, payload = self.transition(
            "live-reward", "residual-accepted", evidence_manifest=evidence
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("residual-acceptance-required", self.violation_kinds(payload))

        acceptance_dir = self.batch_dir / "acceptances"
        acceptance_dir.mkdir()
        acceptance = acceptance_dir / "live-reward.json"
        acceptance.write_text(
            json.dumps(
                {
                    "version": 1,
                    "batch_id": "course-20260715-wave-01",
                    "workflow_id": "live-reward",
                    "risk_ids": ["issues/01"],
                    "accepted_by": "workspace-user",
                    "accepted_at": self.timestamp(),
                    "decision_source": "使用人明确接受 issues/01 剩余风险。",
                    "scope": "residual-risk-only",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        accepted, accepted_payload = self.run_script(
            "accept-residual",
            "--run-file",
            str(self.run_file),
            "--workflow",
            "live-reward",
            "--evidence-manifest",
            str(evidence),
            "--acceptance-file",
            str(acceptance),
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        )

        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertEqual(accepted_payload["terminal_workflows"], 1)
        self.assertEqual(self.state()["workflows"][0]["status"], "residual-accepted")

    def test_branch_drift_invalidates_live_boundary_audit(self) -> None:
        self.write_manifest()
        self.seal()
        audited, _ = self.audit("live-reward")
        self.assertEqual(audited.returncode, 0, audited.stderr)
        subprocess.run(
            ["git", "switch", "-c", "external-branch"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        )

        result, payload = self.transition(
            "live-reward", "in-progress", evidence="PLAN.md#red"
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("boundary-audit-stale", self.violation_kinds(payload))

    def test_production_source_diff_blocks_boundary_audit(self) -> None:
        self.write_manifest()
        self.seal()
        source = self.repository / "src/main/java/example/Unsafe.java"
        source.parent.mkdir(parents=True)
        source.write_text("class Unsafe {}\n", encoding="utf-8")

        result, payload = self.audit("live-reward")

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("prohibited-repository-path", self.violation_kinds(payload))

    def test_transfer_writer_reassigns_writer(self) -> None:
        self.write_manifest()
        self.seal()
        transferred, payload = self.run_script(
            "transfer-writer",
            "--run-file",
            str(self.run_file),
            "--new-writer",
            "replacement-writer",
            "--reason",
            "Original writer stopped and released the role.",
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            "0",
            "--format",
            "json",
        )
        self.assertEqual(transferred.returncode, 0, transferred.stdout + transferred.stderr)
        self.assertEqual(payload["writer"], "replacement-writer")
        self.assertEqual(self.state()["writer"], "replacement-writer")

        rejected, rejected_payload = self.audit("live-reward", actor="root")
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("writer-lease-mismatch", self.violation_kinds(rejected_payload))
        accepted, _ = self.audit("live-reward", actor="replacement-writer")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

    def test_transfer_writer_requires_coordinator(self) -> None:
        self.write_manifest()
        self.seal()
        rejected, payload = self.run_script(
            "transfer-writer",
            "--run-file",
            str(self.run_file),
            "--new-writer",
            "replacement-writer",
            "--reason",
            "Impostor tries to seize the writer role.",
            "--actor",
            "not-the-coordinator",
            "--at",
            self.timestamp(),
            "--expected-revision",
            "0",
            "--format",
            "json",
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("coordinator-mismatch", self.violation_kinds(payload))
        self.assertEqual(self.state()["writer"], "root")

    def test_parallel_workflows_run_concurrently_in_worktrees(self) -> None:
        self.setup_parallel()

        self.start("live-reward", actor="writer-live-reward")
        self.start("live-room", actor="writer-live-room")

        state = self.state()
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["workflows"][0]["status"], "in-progress")
        self.assertEqual(state["workflows"][1]["status"], "in-progress")
        # Compatibility mirror: with several in progress, current_workflow_id
        # is the most recently started workflow.
        self.assertEqual(state["current_workflow_id"], "live-room")

        self.complete("live-reward", actor="writer-live-reward")

        state = self.state()
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["workflows"][0]["status"], "complete")
        self.assertEqual(state["workflows"][1]["status"], "in-progress")
        self.assertEqual(state["current_workflow_id"], "live-room")
        worktree_docs = (
            self.workspace
            / ".scratch/course-test-campaign/worktrees/live-reward/docs/tests/live-reward-tests"
        )
        self.assertTrue((worktree_docs / "REPORT.md").is_file())

    def test_parallel_interleaved_audits_couple_per_workflow(self) -> None:
        # Sequential coupling demands the audit at revision index-1; parallel
        # coupling only demands the most recent audit for the SAME workflow,
        # so another workflow's audit may interleave.
        self.setup_parallel()

        audited_a, _ = self.audit("live-reward", actor="writer-live-reward")
        self.assertEqual(audited_a.returncode, 0, audited_a.stdout + audited_a.stderr)
        audited_b, _ = self.audit("live-room", actor="writer-live-room")
        self.assertEqual(audited_b.returncode, 0, audited_b.stdout + audited_b.stderr)

        started, payload = self.transition(
            "live-reward", "in-progress", evidence="PLAN.md#red", actor="writer-live-reward"
        )

        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertEqual(payload["current_workflow_id"], "live-reward")

    def test_parallel_worktree_audit_rejects_other_workflows_scopes(self) -> None:
        self.setup_parallel()
        worktree = self.workspace / ".scratch/course-test-campaign/worktrees/live-reward"

        own_test = worktree / "mod-a/src/test/java/OwnTest.java"
        own_test.parent.mkdir(parents=True)
        own_test.write_text("class OwnTest {}\n", encoding="utf-8")
        audited, payload = self.audit("live-reward", actor="writer-live-reward")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

        foreign_test = worktree / "mod-b/src/test/java/ForeignTest.java"
        foreign_test.parent.mkdir(parents=True)
        foreign_test.write_text("class ForeignTest {}\n", encoding="utf-8")
        audited, payload = self.audit("live-reward", actor="writer-live-reward")
        self.assertEqual(audited.returncode, 2, audited.stdout + audited.stderr)
        self.assertIn("prohibited-repository-path", self.violation_kinds(payload))

        foreign_test.unlink()
        foreign_docs = worktree / "docs/tests/live-room-tests/REPORT.md"
        foreign_docs.parent.mkdir(parents=True)
        foreign_docs.write_text("# 越界文档\n", encoding="utf-8")
        audited, payload = self.audit("live-reward", actor="writer-live-reward")
        self.assertEqual(audited.returncode, 2, audited.stdout + audited.stderr)
        self.assertIn("prohibited-repository-path", self.violation_kinds(payload))

    def test_parallel_same_module_start_is_rejected(self) -> None:
        def same_module(manifest: dict) -> None:
            for workflow in manifest["workflows"]:
                workflow["module_id"] = "mod-a"

        self.setup_parallel(mutate=same_module)
        self.start("live-reward", actor="writer-live-reward")
        audited, _ = self.audit("live-room", actor="writer-live-room")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

        rejected, payload = self.transition(
            "live-room", "in-progress", evidence="PLAN.md#red", actor="writer-live-room"
        )

        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("module-write-conflict", self.violation_kinds(payload))

    def test_parallel_shared_build_file_start_is_rejected(self) -> None:
        def shared_pom(manifest: dict) -> None:
            for workflow in manifest["workflows"]:
                workflow["test_build_files"] = ["pom.xml"]

        self.setup_parallel(mutate=shared_pom)
        self.start("live-reward", actor="writer-live-reward")
        audited, _ = self.audit("live-room", actor="writer-live-room")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

        rejected, payload = self.transition(
            "live-room", "in-progress", evidence="PLAN.md#red", actor="writer-live-room"
        )

        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("shared-build-file-conflict", self.violation_kinds(payload))

    def test_parallel_concurrency_cap_blocks_second_start(self) -> None:
        self.setup_parallel(max_concurrent=1)
        self.start("live-reward", actor="writer-live-reward")
        audited, _ = self.audit("live-room", actor="writer-live-room")
        self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)

        rejected, payload = self.transition(
            "live-room", "in-progress", evidence="PLAN.md#red", actor="writer-live-room"
        )

        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("concurrency-limit-exceeded", self.violation_kinds(payload))

    def test_parallel_missing_worktree_blocks_audit(self) -> None:
        self.setup_parallel(worktrees=False)

        result, payload = self.audit("live-reward", actor="writer-live-reward")

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("worktree-missing", self.violation_kinds(payload))

    @staticmethod
    def violation_kinds(payload: dict) -> list[str]:
        return [violation["kind"] for violation in payload.get("violations", [])]


if __name__ == "__main__":
    unittest.main()


def load_batch_run_module():
    import importlib.util
    import sys

    scripts_dir = str(SCRIPT.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("batch_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TicketIdGrammarTest(unittest.TestCase):
    def load_module(self):
        return load_batch_run_module()

    def test_ticket_id_from_filename_covers_shared_grammar(self) -> None:
        module = self.load_module()

        self.assertEqual(
            module.ticket_id_from_filename("coupon-20260714-01-double-issue.md"),
            "coupon-20260714-01",
        )
        self.assertEqual(module.ticket_id_from_filename("42-legacy.md"), "42")
        self.assertEqual(module.ticket_id_from_filename("42.md"), "42")
        self.assertEqual(module.ticket_id_from_filename("wf1-01-slug.md"), "wf1-01")
        self.assertIsNone(module.ticket_id_from_filename("-bad.md"))
        self.assertIsNone(module.ticket_id_from_filename("no-numeric-segment.md"))


class ResidualAcceptanceBatchGateTest(unittest.TestCase):
    """paused 批不得绕过 resume 协议直接终结工作流（accept-residual 批状态门禁）。"""

    @staticmethod
    def sequential_payload(transitions):
        return {
            "execution_mode": "sequential",
            "selection": {"approved_at": "2026-07-17T00:00:00+00:00"},
            "agent_policy": {"coordinator": "coordinator", "initial_writer": "writer-1"},
            "workflows": [{"workflow_id": "wf-a", "order": 1}],
            "transitions": transitions,
        }

    @staticmethod
    def event(revision, minute, **fields):
        return {
            "revision": revision,
            "at": f"2026-07-17T00:{minute:02d}:00+00:00",
            **fields,
        }

    def test_paused_batch_rejects_direct_residual_acceptance(self) -> None:
        module = load_batch_run_module()
        payload = self.sequential_payload(
            [
                self.event(
                    1, 1, event="boundary-audit", workflow_id="wf-a",
                    actor="writer-1", audit_fingerprint="fp-1",
                ),
                self.event(
                    2, 2, event="workflow-transition", workflow_id="wf-a",
                    to="in-progress", actor="writer-1", audit_fingerprint="fp-1",
                ),
                self.event(3, 3, event="batch-paused", actor="writer-1", reason="ops"),
                self.event(
                    4, 4, event="boundary-audit", workflow_id="wf-a",
                    actor="writer-1", audit_fingerprint="fp-2",
                ),
                self.event(
                    5, 5, event="residual-accepted", workflow_id="wf-a",
                    actor="coordinator", audit_fingerprint="fp-2",
                ),
            ]
        )

        state, violations = module.replay_journal(payload)

        self.assertTrue(violations, "paused 批直接 accept-residual 必须在重放中被拒")
        self.assertEqual(state["status"], "paused")
        self.assertIsNotNone(state["pause"])
        self.assertEqual(state["workflow_statuses"]["wf-a"]["status"], "in-progress")

    def test_resume_protocol_then_residual_acceptance_replays_clean(self) -> None:
        module = load_batch_run_module()
        payload = self.sequential_payload(
            [
                self.event(
                    1, 1, event="boundary-audit", workflow_id="wf-a",
                    actor="writer-1", audit_fingerprint="fp-1",
                ),
                self.event(
                    2, 2, event="workflow-transition", workflow_id="wf-a",
                    to="in-progress", actor="writer-1", audit_fingerprint="fp-1",
                ),
                self.event(3, 3, event="batch-paused", actor="writer-1", reason="ops"),
                self.event(
                    4, 4, event="boundary-audit", workflow_id="wf-a",
                    actor="writer-1", audit_fingerprint="fp-2",
                ),
                self.event(
                    5, 5, event="batch-resumed", actor="writer-1",
                    audit_fingerprint="fp-2",
                ),
                self.event(
                    6, 6, event="boundary-audit", workflow_id="wf-a",
                    actor="writer-1", audit_fingerprint="fp-3",
                ),
                self.event(
                    7, 7, event="residual-accepted", workflow_id="wf-a",
                    actor="coordinator", audit_fingerprint="fp-3",
                ),
            ]
        )

        state, violations = module.replay_journal(payload)

        self.assertEqual(violations, [], violations)
        self.assertEqual(state["status"], "complete")
        self.assertIsNone(state["pause"])
        self.assertEqual(
            state["workflow_statuses"]["wf-a"]["status"], "residual-accepted"
        )


class MalformedRunFileRobustnessTest(BatchRunStateTest):
    def test_missing_order_key_reports_structured_error_not_traceback(self) -> None:
        self.write_manifest()
        self.seal()

        def drop_order(payload: dict) -> None:
            del payload["workflows"][1]["order"]

        self.mutate_run_file(drop_order)
        result, payload = self.run_script(
            "validate", "--run-file", str(self.run_file), "--format", "json"
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertTrue(payload.get("violations"), result.stdout + result.stderr)


class WorktreeDriftAndPerWorkflowWriterTest(BatchRunStateTest):
    """补齐 verify_worktree 三个漂移否决分支与 transfer-writer --workflow 的覆盖。"""

    def worktree_path(self, workflow_id: str) -> Path:
        return self.workspace / f".scratch/course-test-campaign/worktrees/{workflow_id}"

    def test_worktree_branch_drift_blocks_audit(self) -> None:
        self.setup_parallel()
        subprocess.run(
            ["git", "checkout", "-q", "-b", "hijack"],
            cwd=self.worktree_path("live-reward"),
            check=True,
            capture_output=True,
        )

        result, payload = self.audit("live-reward", actor="writer-live-reward")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("worktree-branch-drift", self.violation_kinds(payload))

    def test_worktree_head_drift_blocks_audit(self) -> None:
        self.setup_parallel()
        worktree = self.worktree_path("live-reward")
        extra = worktree / "mod-a/src/test/java/Advance.java"
        extra.parent.mkdir(parents=True)
        extra.write_text("class Advance {}\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "."], cwd=worktree, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-qm", "advance"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        result, payload = self.audit("live-reward", actor="writer-live-reward")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("worktree-head-drift", self.violation_kinds(payload))

    def test_foreign_repository_at_worktree_path_blocks_audit(self) -> None:
        self.setup_parallel()
        worktree = self.worktree_path("live-reward")
        shutil.rmtree(worktree)
        worktree.mkdir(parents=True)
        subprocess.run(
            ["git", "init", "-q", "-b", "ut-parallel-live-reward"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        result, payload = self.audit("live-reward", actor="writer-live-reward")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("worktree-not-of-repository", self.violation_kinds(payload))

    def test_transfer_writer_per_workflow_reassigns_only_that_lease(self) -> None:
        self.setup_parallel()
        transferred, _ = self.run_script(
            "transfer-writer",
            "--run-file",
            str(self.run_file),
            "--workflow",
            "live-reward",
            "--new-writer",
            "writer-substitute",
            "--reason",
            "原写者停止，坐标者换人。",
            "--actor",
            "root",
            "--at",
            self.timestamp(),
            "--expected-revision",
            str(self.state()["revision"]),
            "--format",
            "json",
        )
        self.assertEqual(transferred.returncode, 0, transferred.stdout + transferred.stderr)

        rejected, payload = self.audit("live-reward", actor="writer-live-reward")
        self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
        self.assertIn("writer-lease-mismatch", self.violation_kinds(payload))

        accepted, _ = self.audit("live-reward", actor="writer-substitute")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        untouched, _ = self.audit("live-room", actor="writer-live-room")
        self.assertEqual(untouched.returncode, 0, untouched.stdout + untouched.stderr)
