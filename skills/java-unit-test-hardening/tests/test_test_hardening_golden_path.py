"""黄金路径 E2E：模板逐字面 materialize 后，全校验链必须零违规通过。

契约：机器键行（含其 `<!-- … -->` / ` # …` 行尾注释）逐字面保留，`<…>` 占位符替换为
具体值。materialize() 对每个替换片段断言"模板中存在"，因此模板结构漂移会让本文件
先于真实 campaign 失败——组件间契约（模板 ↔ 校验器 ↔ triage）由此受保护。
"""

import json
import subprocess
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL_ROOT / "assets/templates"
SCRIPTS = SKILL_ROOT / "scripts"
BASELINE_SHA = "0123456789abcdef0123456789abcdef01234567"
TICKET_FILE = "COURSE-01-001-checkout-double-charge.md"
ARTIFACT_DIR_RELATIVE = ".scratch/course-baseline-tests/course-video-tests"


def materialize(template: str, replacements: dict[str, str]) -> str:
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert old in text, f"{template} 模板缺少预期片段（模板漂移？）: {old!r}"
        text = text.replace(old, new)
    return text


def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def build_campaign(workspace: Path) -> tuple[Path, Path, Path]:
    """materialize 一个 in-progress 服务 campaign + 一个 complete 工作流。"""
    campaign = workspace / ".scratch/course-test-campaign"
    artifacts_root = workspace / ".scratch/course-baseline-tests"
    workflow_dir = workspace / ARTIFACT_DIR_RELATIVE
    (workflow_dir / "issues").mkdir(parents=True)
    campaign.mkdir(parents=True)

    (workflow_dir / "PRD.md").write_text(
        materialize(
            "PRD.md",
            {
                "campaign-status: draft <!--": "campaign-status: complete <!--",
            },
        ),
        encoding="utf-8",
    )

    (workflow_dir / "PLAN.md").write_text(
        materialize(
            "PLAN.md",
            {
                '<精确记录下一阶段、文件、阻塞事实和命令；不得写泛化的“继续”。record-only-confirmed 下不得把生产修复授权写成待办或阻塞项。>': (
                    "campaign 已关闭；无待办。"
                ),
            },
        ),
        encoding="utf-8",
    )

    (workflow_dir / "REPORT.md").write_text(
        materialize(
            "REPORT.md",
            {
                "`issues/<n>`": "`issues/COURSE-01-001`",
            },
        ),
        encoding="utf-8",
    )

    (workflow_dir / "BEHAVIOR-MATRIX.md").write_text(
        materialize("BEHAVIOR-MATRIX.md", {}), encoding="utf-8"
    )

    (workflow_dir / "issues" / TICKET_FILE).write_text(
        materialize(
            "BUG-TICKET.md",
            {
                "characterization-tests: `<TestClass#method>`": (
                    "characterization-tests: "
                    "`CourseOrderServiceTest#chargeTwiceKeepsSingleDebit`"
                ),
                '<For record-only-confirmed: "Production fix is out of scope for the '
                'current campaign; retain as an unresolved risk." For '
                "authorized-ticket-scoped: minimal fix and verification. Do not ask "
                "to change the policy here.>": (
                    "Production fix is out of scope for the current campaign; "
                    "retain as an unresolved risk."
                ),
            },
        ),
        encoding="utf-8",
    )

    (campaign / "BACKLOG.md").write_text(
        materialize(
            "BACKLOG.md",
            {
                "service-baseline: <full Git SHA>": f"service-baseline: {BASELINE_SHA}",
                "| <stable-id> | <module-id> | yes | P0 | <workflow> | pending "
                "| — | — | — | — | none | — | — |": (
                    "| course-video | root | yes | P0 | 课程视频交付 | complete "
                    f"| — | ut-20260717-0123456-course-video | main | {BASELINE_SHA} "
                    f"| {ARTIFACT_DIR_RELATIVE} | — | 1 |"
                ),
                "| <date> | <module-id> | <baseline> | <baseline> | 0 | <count> |": (
                    "| 2026-07-17 | root | 41% | 33% | 1 | 1 |"
                ),
                "<Exact active batch, next module, workflow, and phase; blockers, "
                "decisions, files, and commands needed to resume. Never recommend "
                "another service while a core row is non-terminal.>": (
                    "course-video 已完成；其余核心行待盘点。"
                ),
            },
        ),
        encoding="utf-8",
    )

    (campaign / "CORE-FLOW-INVENTORY.md").write_text(
        materialize(
            "CORE-FLOW-INVENTORY.md",
            {
                "inventory-head: <full Git SHA used for the code inventory>": (
                    f"inventory-head: {BASELINE_SHA}"
                ),
                "| <stable-module-id> | <repository-relative path> | partial "
                "| 0 | 0 | 0 | <tool/query and code evidence> |": (
                    "| root | . | partial | 1 | 1 | 0 | CodeGraph search_callers 证据 |"
                ),
                "| <stable-flow-id> | <module-id> "
                "| <Controller/RPC/listener/job/service symbols> | <workflow-id> "
                "| yes | <call-path evidence and risk basis> |": (
                    "| flow-course-video | root | CourseVideoController#deliver "
                    "| course-video | yes | CodeGraph 调用链 |"
                ),
                "- <Entry symbol, reason, owner/evidence. Do not use package names "
                "or low coverage alone as an exclusion reason.>": "- none",
            },
        ),
        encoding="utf-8",
    )

    return campaign, artifacts_root, workflow_dir


def test_workflow_artifacts_from_templates_pass_campaign_validator(tmp_path):
    _, _, workflow_dir = build_campaign(tmp_path)

    result = run_script(
        "validate_campaign.py", "--campaign-dir", str(workflow_dir), "--format", "json"
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["result"] == "VALID", payload
    assert payload["production_fix_policy"] == "record-only-confirmed"


def test_service_campaign_from_templates_passes_service_validator(tmp_path):
    campaign, _, _ = build_campaign(tmp_path)

    result = run_script(
        "validate_service_campaign.py",
        "--workspace-root",
        str(tmp_path),
        "--campaign-root",
        str(campaign),
        "--format",
        "json",
    )
    payload = json.loads(result.stdout) if result.stdout else {}

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["result"] == "VALID", payload
    assert payload["service_campaign_status"] == "in-progress"
    assert payload["closure_ready"] is False


def test_triage_index_generates_and_verifies_over_template_ticket(tmp_path):
    _, artifacts_root, _ = build_campaign(tmp_path)

    generate = run_script("generate_triage.py", "--root", str(artifacts_root))
    assert generate.returncode == 0, generate.stdout + generate.stderr

    markdown = (artifacts_root / "TRIAGE.md").read_text(encoding="utf-8")
    assert "P0 1 · P1 0 · P2 0" in markdown, markdown
    assert f"[COURSE-01-001](course-video-tests/issues/{TICKET_FILE})" in markdown

    check = run_script("generate_triage.py", "--root", str(artifacts_root), "--check")
    assert check.returncode == 0, check.stdout + check.stderr
