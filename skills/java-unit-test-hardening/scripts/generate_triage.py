#!/usr/bin/env python3
"""从各 issue 票的 priority/verification/severity 字段聚合出修复优先级索引 TRIAGE.md。

只读递归扫描 `<root>/**/<workflow>/issues/*.md`,按 priority 分组、severity 次序排列,写出
`<root>/TRIAGE.md`。这是一个视图/索引,不移动任何 issue 文件——issue 与其行为矩阵、
REPORT、回归测试仍同处保存。priority 由票据的 verification+severity 派生;字段缺失时
如实标为未知,不猜测。即使当前没有 issue 也生成空索引，使它从首个 workflow 起就是稳定
存在的 campaign 核心产物。人工核验结果从已有索引中按票据链接保留，新票据默认待核验。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PENDING_MANUAL_REVIEW = "待核验"
# 票据 ID 统一文法（与 batch_run.py / validate_campaign.py 保持一致）：
# 纯数字遗留 ID，或 `<领域>-<批次>-<序号>` 形式的字母数字域 + 至少一个数字段。
TICKET_ID_GRAMMAR = r"\d+|[A-Za-z][A-Za-z0-9]*(?:-\d+)+"


def field(text: str, names: str) -> str:
    match = re.search(rf"(?m)^\s*(?:{names})\s*[:：]\s*(.+?)\s*$", text)
    if not match:
        return ""
    # 模板允许机器键行尾携带 `<!-- … -->` / ` # …` 枚举说明注释，解析时剥除。
    value = match.group(1).split("<!--", 1)[0]
    value = re.split(r"\s#", value, maxsplit=1)[0]
    return value.strip().strip("`").strip()


def impact_snippet(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if re.match(r"^##\s*(Impact|影响|复现与影响|复现)", line, re.IGNORECASE):
            for candidate in lines[index + 1 : index + 6]:
                stripped = candidate.strip()
                if stripped and not stripped.startswith("<"):
                    return stripped[:60]
    return ""


def collect(root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(root.rglob("issues/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        title = lines[0].lstrip("# ").strip() if lines else path.name
        items.append(
            {
                "priority": field(text, "priority") or "P?",
                "verification": field(text, "verification") or "?",
                "severity": field(text, "severity") or "?",
                "workflow": path.parent.parent.name.removesuffix("-tests"),
                "id": ticket_id(path),
                "title": title,
                "impact": impact_snippet(lines),
                "rel": path.relative_to(root).as_posix(),
            }
        )
    return items


def ticket_id(path: Path) -> str:
    """从 `<票据ID>[-<slug>].md` 提取稳定票据 ID（文法与 batch_run.py 一致）。

    无法识别的历史文件保留完整 stem，避免像旧实现一样静默截成首个连字号前缀。
    """
    match = re.match(rf"^({TICKET_ID_GRAMMAR})(?:-|$)", path.stem)
    return match.group(1) if match else path.stem


def collect_manual_reviews(target: Path) -> dict[str, str]:
    if not target.is_file():
        return {}
    reviews: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) != 6:
            continue
        ticket = re.fullmatch(r"\[[^]]+\]\((.+)\)", cells[0])
        if ticket and cells[4]:
            reviews[ticket.group(1)] = cells[4]
    return reviews


def table(
    rows: list[dict[str, Any]], manual_reviews: dict[str, str] | None = None
) -> str:
    if not rows:
        return "（无）"
    reviews = manual_reviews or {}
    out = [
        "| 票据 | 严重度 | 验证 | 工作流 | 人工核验（是否修复） | 摘要 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        summary = row["title"][:32] + (("｜" + row["impact"]) if row["impact"] else "")
        manual_review = reviews.get(row["rel"], PENDING_MANUAL_REVIEW)
        out.append(
            f"| [{row['id']}]({row['rel']}) | {row['severity']} | "
            f"{row['verification']} | {row['workflow']} | {manual_review} | {summary} |"
        )
    return "\n".join(out)


def render(
    items: list[dict[str, Any]], manual_reviews: dict[str, str] | None = None
) -> str:
    ordered = sorted(
        items,
        key=lambda r: (
            PRIORITY_ORDER.get(r["priority"], 9),
            SEVERITY_ORDER.get(r["severity"], 9),
            r["workflow"],
        ),
    )
    counts = Counter(r["priority"] for r in ordered)

    def tier(priority: str) -> list[dict[str, Any]]:
        return [r for r in ordered if r["priority"] == priority]

    unknown = [r for r in ordered if r["priority"] not in PRIORITY_ORDER]
    unknown_block = (
        f"\n## ⚪ 未定级（票据缺 priority 字段，请补）\n\n"
        f"{table(unknown, manual_reviews)}\n"
        if unknown
        else ""
    )
    return f"""# 缺陷修复优先级索引(TRIAGE)

> 视图/索引,不搬迁文件。每条 issue 仍在 `<module>/<workflow>/issues/` 下,与行为矩阵、REPORT、
> `@Disabled` 回归测试同处保存(修复时完整上下文一点即到)。修复排期从 P0 自上而下推进。
>
> `priority` 由每张票的 `verification`+`severity` 派生:`confirmed+high=P0`、
> `confirmed+medium=P1`、`suspected 或 latent 或 test-hygiene=P2`。`verification` 反映该
> campaign 自身的确认程度(`confirmed`=已抽验 / `suspected`=需业务确认 / `latent`=未开票)。
> 若票据带"启发式待复核"注释,以票据注释为准。
>
> `人工核验（是否修复）` 由负责人填写：`修复`、`不修复（注明原因）` 或 `待核验`；
> 默认值为 `待核验`，自动优先级不能替代人工决定。

统计:**P0 {counts['P0']} · P1 {counts['P1']} · P2 {counts['P2']}**（共 {len(ordered)}）。

---

## 🔴 P0 — 立即修（confirmed + 高危：资金/写覆盖/数据完整性）

{table(tier("P0"), manual_reviews)}

## 🟠 P1 — 排期修（confirmed + 中危：NPE/一致性/幂等/边界/隔离）

{table(tier("P1"), manual_reviews)}

## 🟡 P2 — 先与业务确认（suspected / latent / test-hygiene）

{table(tier("P2"), manual_reviews)}
{unknown_block}
---

*由各 issue 票的 priority/verification/severity 字段自动汇总;字段与本页如有出入,以票据为准。*
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 issue 票的 priority 字段生成 TRIAGE.md 修复优先级索引"
    )
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
        help="扫描根,递归包含 <workflow>/issues/*.md;TRIAGE.md 写入此处",
    )
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--stdout", action="store_true", help="打印到 stdout 而非写入 TRIAGE.md"
    )
    output_mode.add_argument(
        "--check",
        action="store_true",
        help="校验现有 TRIAGE.md 与当前 issue 集合完全一致，不写文件",
    )
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"根目录不存在:{root}", file=sys.stderr)
        return 2
    items = collect(root)
    target = root / "TRIAGE.md"
    markdown = render(items, collect_manual_reviews(target))
    if args.check:
        if not target.is_file():
            print(f"缺少核心 campaign 索引:{target}", file=sys.stderr)
            return 2
        if target.read_text(encoding="utf-8") != markdown:
            print(f"TRIAGE.md 已过期，请重新生成:{target}", file=sys.stderr)
            return 2
        print(f"TRIAGE.md 有效（{len(items)} issue）")
        return 0
    if args.stdout:
        print(markdown)
    else:
        target.write_text(markdown, encoding="utf-8")
        print(f"已生成 {target}（{len(items)} issue）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
