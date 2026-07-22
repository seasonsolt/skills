import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SCRIPT = (
    SKILL_ROOT
    / "scripts/validate_campaign.py"
)


class CampaignValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.campaign = Path(self.temporary_directory.name)
        (self.campaign / "issues").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_campaign(
        self,
        *,
        policy: str = "record-only-confirmed",
        plan: str = "Production-fix policy snapshot: `record-only-confirmed`\n",
        issue: str | None = None,
        authorized_tickets: str = "none",
        campaign_status: str = "in-progress",
        report: str = "Residual risk: issues/01 remains recorded.\n",
    ) -> None:
        if issue is None:
            issue = (
                "# 缺陷票据\n\n"
                "status: recorded\n"
                "finding-type: defect\n"
                "verification: confirmed\n"
                "severity: medium\n"
                "priority: P1\n"
                "characterization-tests: `ExampleBehaviorTest#currentBehavior`\n"
                "regression-tests: `ExampleBehaviorTest#expectedBehavior`\n\n"
                "Production fix is out of scope for the current campaign.\n"
            )
        (self.campaign / "PRD.md").write_text(
            f"campaign-status: {campaign_status}\n"
            "ticket-evidence-version: 1\n"
            f"production-fix-policy: {policy}\n"
            f"authorized-fix-tickets: {authorized_tickets}\n",
            encoding="utf-8",
        )
        (self.campaign / "PLAN.md").write_text(plan, encoding="utf-8")
        (self.campaign / "REPORT.md").write_text(report, encoding="utf-8")
        (self.campaign / "issues/01-defect.md").write_text(issue, encoding="utf-8")

    def run_validator(self) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--campaign-dir",
                str(self.campaign),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result, json.loads(result.stdout)

    def test_case_counts_are_evidence_not_a_closure_gate(self) -> None:
        self.write_campaign()
        prd = self.campaign / "PRD.md"
        prd.write_text(
            "\n".join(
                line
                for line in prd.read_text(encoding="utf-8").splitlines()
                if not line.startswith("planned-")
            )
            + "\n",
            encoding="utf-8",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")

    def test_template_style_inline_comments_are_ignored_on_machine_lines(self) -> None:
        self.write_campaign(
            policy=(
                "record-only-confirmed"
                " <!-- record-only-confirmed | authorized-ticket-scoped -->"
            ),
            authorized_tickets="none <!-- authorized-ticket-scoped 时填写 issues/<ticket-id> -->",
            issue=(
                "# 缺陷票据\n\n"
                "status: recorded\n"
                "finding-type: defect # defect | suspected | test-hygiene\n"
                "verification: confirmed # confirmed(生产代码已抽验) | suspected | latent\n"
                "severity: medium # high | medium | low\n"
                "priority: P1 # 由 verification+severity 派生\n"
                "characterization-tests: `ExampleBehaviorTest#currentBehavior` # 逗号分隔\n"
                "regression-tests: `ExampleBehaviorTest#expectedBehavior` # confirmed defect 必填\n\n"
                "Production fix is out of scope for the current campaign.\n"
            ),
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")

    def test_authorized_ticket_scoped_accepts_full_ticket_id_grammar(self) -> None:
        self.write_campaign(
            policy="authorized-ticket-scoped",
            authorized_tickets="issues/coupon-20260714-01, issues/42",
            plan="Production-fix policy snapshot: `authorized-ticket-scoped`\n",
        )

        _, payload = self.run_validator()

        self.assertNotEqual(payload["result"], "POLICY_INVALID", payload)

    def test_authorized_ticket_scoped_rejects_malformed_ticket_list(self) -> None:
        self.write_campaign(
            policy="authorized-ticket-scoped",
            authorized_tickets="fix everything",
            plan="Production-fix policy snapshot: `authorized-ticket-scoped`\n",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(payload["result"], "POLICY_INVALID")

    def test_record_only_campaign_accepts_out_of_scope_resolution(self) -> None:
        self.write_campaign()

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")
        self.assertEqual(payload["production_fix_policy"], "record-only-confirmed")

    def test_record_only_defect_does_not_require_disabled_future_regression(self) -> None:
        self.write_campaign(
            issue=(
                "status: recorded\n"
                "finding-type: defect\n"
                "verification: confirmed\n"
                "severity: medium\n"
                "priority: P1\n"
                "characterization-tests: `ExampleBehaviorTest#currentBehavior`\n"
            )
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")

    def test_confirmed_ticket_rejects_summary_without_traceable_badcases(self) -> None:
        self.write_campaign(
            issue=(
                "# issues/01 摘要票据\n\n"
                "status: recorded\n"
                "verification: confirmed\n"
                "severity: medium\n"
                "priority: P1\n\n"
                "当前行为和期望回归均已保留测试证据。\n"
            )
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(payload["result"], "TICKET_EVIDENCE_INVALID")
        self.assertEqual(
            {violation["kind"] for violation in payload["violations"]},
            {
                "missing-finding-type",
            },
        )

    def test_confirmed_ticket_rejects_non_method_test_references(self) -> None:
        self.write_campaign(
            issue=(
                "status: recorded\n"
                "finding-type: defect\n"
                "verification: confirmed\n"
                "severity: medium\n"
                "priority: P1\n"
                "characterization-tests: `单元测试`\n"
                "regression-tests: `issues/01`\n"
            )
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(payload["result"], "TICKET_EVIDENCE_INVALID")
        self.assertEqual(
            {violation["kind"] for violation in payload["violations"]},
            {
                "invalid-characterization-test-reference",
                "invalid-regression-test-reference",
            },
        )

    def test_record_only_campaign_accepts_template_markdown_list_snapshot(self) -> None:
        self.write_campaign(
            plan="- production-fix-policy-snapshot: `record-only-confirmed`\n"
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "VALID")

    def test_legacy_campaign_without_ticket_evidence_version_remains_readable(self) -> None:
        self.write_campaign(
            issue="Production fix is out of scope for the current campaign.\n"
        )
        prd = self.campaign / "PRD.md"
        prd.write_text(
            prd.read_text(encoding="utf-8").replace("ticket-evidence-version: 1\n", ""),
            encoding="utf-8",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(payload["ticket_evidence_version"])

    def test_record_only_campaign_rejects_reopened_authorization_question(self) -> None:
        self.write_campaign(
            plan="Next: decide whether to authorize a production fix for issues/01.\n"
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(payload["result"], "POLICY_CONTRADICTION")
        self.assertEqual(payload["violations"][0]["path"], "PLAN.md")

    def test_record_only_campaign_rejects_awaiting_authorization_skip(self) -> None:
        self.write_campaign(
            issue='@Disabled("issues/01 - awaiting production-fix authorization")\n'
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(payload["result"], "POLICY_CONTRADICTION")

    def test_ticket_scoped_authorization_requires_explicit_ticket_list(self) -> None:
        self.write_campaign(
            policy="authorized-ticket-scoped",
            plan="Production-fix policy snapshot: `authorized-ticket-scoped`\n",
        )

        result, payload = self.run_validator()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(payload["result"], "POLICY_INVALID")



if __name__ == "__main__":
    unittest.main()
