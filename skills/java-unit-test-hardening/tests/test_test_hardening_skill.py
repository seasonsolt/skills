import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class TestHardeningSkillContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    def test_skill_is_explicit_only(self) -> None:
        self.assertIn("invocation: explicit-only", self.skill)
        self.assertIn("$java-unit-test-hardening", self.skill)
        self.assertIn("Python 3.10+", self.skill)
        self.assertIn("macOS/Linux", self.skill)
        agent = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: false", agent)

    def test_skill_accepts_direct_repository_without_workspace_contract(self) -> None:
        self.assertIn("--repository-root", self.skill)
        self.assertIn("--campaign-workspace", self.skill)
        self.assertIn("目标仓库之外", self.skill)
        self.assertNotIn("system-context/", self.skill)
        self.assertNotIn("WORKFLOW-LOCAL.yaml", self.skill)
        self.assertNotIn("services/<service>", self.skill)
        self.assertNotIn("TAPD", self.skill)
        self.assertNotIn("OpenSpec", self.skill)

    def test_bundled_paths_are_install_location_independent(self) -> None:
        self.assertIn("<skill-root>/scripts/preflight.py", self.skill)
        self.assertNotIn(".codex/skills/java-unit-test-hardening", self.skill)
        self.assertNotIn(".agents/skills/java-unit-test-hardening", self.skill)

    def test_codegraph_is_optional_not_a_hard_dependency(self) -> None:
        self.assertIn("若环境已提供 CodeGraph", self.skill)
        self.assertIn("不要把某个外部索引工具设为公共 skill 的必需依赖", self.skill)
        preflight = (SKILL_ROOT / "scripts/preflight.py").read_text(encoding="utf-8")
        self.assertNotIn("import yaml", preflight)
        self.assertNotIn("system-context", preflight)
        self.assertNotIn("codegraph", preflight.lower())

    def test_campaign_starts_from_clean_worktree(self) -> None:
        self.assertIn("WORKTREE_NOT_CLEAN", self.skill)
        self.assertIn("完全干净", self.skill)
        self.assertNotIn("--entry-decision-file", self.skill)
        self.assertFalse((SKILL_ROOT / "assets/templates/ENTRY-DECISION.json").exists())

    def test_batch_contract_has_no_duplicate_goal_grant_or_state_mirrors(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "assets/templates/BATCH-RUN.json").read_text(
                encoding="utf-8"
            )
        )
        for key in (
            "goal_contract",
            "goal_objective",
            "batch_grants",
            "status",
            "writer",
            "revision",
            "current_workflow_id",
            "last_boundary_audit",
        ):
            self.assertNotIn(key, template)
        self.assertNotIn("status", template["workflows"][0])
        self.assertNotIn("evidence", template["workflows"][0])
        self.assertEqual(template["execution_mode"], "sequential")
        self.assertIn("external-campaign-workspace", template["workspace_root"])

    def test_case_counts_are_not_completion_gates(self) -> None:
        template = (SKILL_ROOT / "assets/templates/PRD.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("planned-unit-test-cases-min", template)
        self.assertNotIn("planned-integration-test-cases-min", template)
        self.assertIn("不设置通用", self.skill)

    def test_class_size_coverage_gate_is_removed(self) -> None:
        self.assertFalse(
            (SKILL_ROOT / "scripts/generate_core_coverage_evidence.py").exists()
        )
        self.assertFalse(
            (SKILL_ROOT / "assets/templates/CORE-COVERAGE-EVIDENCE.json").exists()
        )
        self.assertIn("覆盖率数字代替业务行为验证", self.skill)

    def test_record_only_defect_needs_characterization_not_disabled_future_test(
        self,
    ) -> None:
        ticket = (SKILL_ROOT / "assets/templates/BUG-TICKET.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("regression-tests: none", ticket)
        self.assertIn("不要预先创建禁用", self.skill)

    def test_atomic_advance_is_the_normal_transition_interface(self) -> None:
        self.assertIn("advance", self.skill)
        self.assertIn("同一文件锁内", self.skill)
        script = (SKILL_ROOT / "scripts/batch_run.py").read_text(encoding="utf-8")
        self.assertIn('(\"advance\", \"transition\")', script)

    def test_tdd_inner_loop_is_module_and_test_scoped(self) -> None:
        self.assertIn("-Dtest=<TestClass>#<method>", self.skill)
        self.assertIn("内循环不运行 `clean`", self.skill)

    def test_core_safety_rules_remain(self) -> None:
        for fragment in (
            "production-fix-policy: record-only-confirmed",
            "authorized-ticket-scoped",
            "不得执行 DDL",
            "一个写域只有一个 writer",
            "不得制造绿色结果",
            "validate_portable_artifacts.py",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.skill)


if __name__ == "__main__":
    unittest.main()
