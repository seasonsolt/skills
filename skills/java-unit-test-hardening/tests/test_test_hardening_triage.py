import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/generate_triage.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("generate_triage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_issue(path: Path, title: str = "租户边界") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {title}\n\npriority: P1\nverification: confirmed\nseverity: medium\n",
        encoding="utf-8",
    )


def test_collect_recurses_through_module_and_preserves_root_relative_link(tmp_path):
    module = load_module()
    issue = (
        tmp_path
        / "mall4cloud-common-exception/exception-capture-tests/issues"
        / "EXC-01-001-default-id-expression-null-unboxing.md"
    )
    write_issue(issue)

    items = module.collect(tmp_path)

    assert len(items) == 1
    assert items[0]["id"] == "EXC-01-001"
    assert items[0]["workflow"] == "exception-capture"
    assert items[0]["rel"] == (
        "mall4cloud-common-exception/exception-capture-tests/issues/"
        "EXC-01-001-default-id-expression-null-unboxing.md"
    )


def test_collect_keeps_support_for_flat_workflow_layout(tmp_path):
    module = load_module()
    issue = tmp_path / "payment-tests/issues/PAY-02-003-duplicate-charge.md"
    write_issue(issue, "重复扣款")

    items = module.collect(tmp_path)

    assert items[0]["id"] == "PAY-02-003"
    assert items[0]["rel"] == "payment-tests/issues/PAY-02-003-duplicate-charge.md"


def test_ticket_id_falls_back_to_complete_stem_for_legacy_names():
    module = load_module()

    assert module.ticket_id(Path("legacy-risk-note.md")) == "legacy-risk-note"


def run_generator(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_generates_core_index_even_when_no_issue_exists(tmp_path):
    result = run_generator(tmp_path)

    assert result.returncode == 0, result.stderr
    triage = (tmp_path / "TRIAGE.md").read_text(encoding="utf-8")
    assert "P0 0 · P1 0 · P2 0" in triage
    assert "（共 0）" in triage
    assert "`人工核验（是否修复）`" in triage


def test_regeneration_preserves_manual_review_and_defaults_new_issue(tmp_path):
    first_issue = tmp_path / "payment-tests/issues/PAY-01-001-risk.md"
    write_issue(first_issue)
    generated = run_generator(tmp_path)
    assert generated.returncode == 0, generated.stderr

    target = tmp_path / "TRIAGE.md"
    triage = target.read_text(encoding="utf-8")
    assert "| 人工核验（是否修复） |" in triage
    assert "| 待核验 |" in triage
    target.write_text(
        triage.replace("| 待核验 |", "| 不修复（已确认风险可接受） |", 1),
        encoding="utf-8",
    )

    valid_after_manual_review = run_generator(tmp_path, "--check")
    assert valid_after_manual_review.returncode == 0, valid_after_manual_review.stderr

    write_issue(tmp_path / "order-tests/issues/ORD-01-001-risk.md")
    refreshed = run_generator(tmp_path)
    assert refreshed.returncode == 0, refreshed.stderr
    refreshed_triage = target.read_text(encoding="utf-8")
    assert "| 不修复（已确认风险可接受） |" in refreshed_triage
    assert refreshed_triage.count("| 待核验 |") == 1


def test_check_rejects_missing_and_stale_index_then_accepts_refresh(tmp_path):
    missing = run_generator(tmp_path, "--check")
    assert missing.returncode == 2
    assert "缺少核心 campaign 索引" in missing.stderr

    write_issue(tmp_path / "payment-tests/issues/PAY-01-001-risk.md")
    generated = run_generator(tmp_path)
    assert generated.returncode == 0, generated.stderr
    valid = run_generator(tmp_path, "--check")
    assert valid.returncode == 0, valid.stderr

    write_issue(tmp_path / "order-tests/issues/ORD-01-001-risk.md")
    stale = run_generator(tmp_path, "--check")
    assert stale.returncode == 2
    assert "TRIAGE.md 已过期" in stale.stderr

    refreshed = run_generator(tmp_path)
    assert refreshed.returncode == 0, refreshed.stderr
    valid_again = run_generator(tmp_path, "--check")
    assert valid_again.returncode == 0, valid_again.stderr


def test_field_strips_backticks_and_trailing_comments(tmp_path):
    module = load_module()
    issue = tmp_path / "mod/wf-tests/issues/EXC-01-001-sample.md"
    issue.parent.mkdir(parents=True)
    issue.write_text(
        "# 样例\n\n"
        "priority: `P0` # 由 verification+severity 派生\n"
        "verification: confirmed <!-- confirmed | suspected | latent -->\n"
        "severity: `high`\n",
        encoding="utf-8",
    )

    items = module.collect(tmp_path)

    assert items[0]["priority"] == "P0"
    assert items[0]["verification"] == "confirmed"
    assert items[0]["severity"] == "high"


def test_ticket_id_uses_shared_grammar_with_batch_run():
    module = load_module()

    assert module.ticket_id(Path("coupon-20260714-01-double-issue.md")) == "coupon-20260714-01"
    assert module.ticket_id(Path("EXC-01-001-default-id.md")) == "EXC-01-001"
    assert module.ticket_id(Path("123-npe-on-null.md")) == "123"
    assert module.ticket_id(Path("wf1-01-slug.md")) == "wf1-01"
    # 无法识别的历史命名保留完整 stem
    assert module.ticket_id(Path("legacy-note.md")) == "legacy-note"
