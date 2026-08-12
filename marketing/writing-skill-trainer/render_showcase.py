#!/usr/bin/env python3
"""Publish a static, secret-free showcase from a completed benchmark run."""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent


def escape(text: object) -> str:
    return html.escape(str(text), quote=True)


def label(condition: str) -> str:
    return {"trained": "训练后", "direct": "直接生成", "tie": "均未通过"}.get(condition, condition)


def score_average(scores: dict[str, float]) -> float:
    return round(mean(scores.values()), 2)


def failure_text(failures: list[str]) -> str:
    return "；".join(failures) if failures else "无"


def render_markdown(data: dict[str, Any]) -> str:
    blind = data["overall_blind_preference"]
    qualified = data["overall_qualified_pairwise_results"]
    usage = data["usage"]
    lines = [
        "# Writing Skill Trainer：DeepSeek 实测",
        "",
        "> 同一个 DeepSeek，不换更强模型：先从样本训练 Writing Skill，再与直接生成做匿名 A/B。",
        "",
        "## 结论",
        "",
        f"- **盲评偏好：训练后 {blind['trained']}/9，直接生成 {blind['direct']}/9。**",
        f"- **通过硬约束后的成对结果：训练后 {qualified['trained']}，直接生成 {qualified['direct']}，双方均未通过 {qualified['tie']}。**",
        f"- 所有训练、生成和评审调用均请求 `deepseek-chat`；API 实际返回 `{', '.join(usage['actual_models'])}`。",
        f"- 共 {usage['api_calls']} 次 API 调用，{usage['tokens']['total_tokens']:,} tokens。",
        "- 18 份生成稿均未触发连续 30 字来源重合警报。",
        "",
        "这里的 7/9 是**匿名写作质量偏好**，不是通过率。严格检查暴露了真实短板：训练后稿件的风格通常更稳定，但长度控制仍会失败；新闻场景两组都未产出完整合格稿。",
        "",
        "| 场景 | 匿名偏好 | 硬约束后结果 | 训练后 / 直接平均机制分 | 结论 |",
        "|---|---:|---:|---:|---|",
    ]
    conclusions = {
        "red-chamber": "训练后在三轮盲评中全胜；一次因超长被直接稿反超。",
        "restrained-satire": "训练后 2:1 获偏好，但两轮长度控制不稳定。",
        "tech-news": "训练后事实性更好，直接稿两轮补造观点；两组均未满足长度门槛。",
    }
    for scenario in data["scenarios"]:
        summary = scenario["summary"]
        lines.append(
            "| {name} | 训练后 {trained}:{direct} 直接 | {qw} | {ts:.2f} / {ds:.2f} | {conclusion} |".format(
                name=scenario["name"],
                trained=summary["blind_preference"]["trained"],
                direct=summary["blind_preference"]["direct"],
                qw="训 {trained} / 直 {direct} / 均失败 {tie}".format(**summary["qualified_pairwise_results"]),
                ts=summary["mean_scores"]["trained"]["mechanism_fidelity"],
                ds=summary["mean_scores"]["direct"]["mechanism_fidelity"],
                conclusion=conclusions[scenario["id"]],
            )
        )

    lines.extend(
        [
            "",
            "## 代表性 A/B 输出",
            "",
            "以下固定展示每个场景的第 1 轮，不按结果挑样。完整 9 轮数据见 [`results/benchmark.json`](results/benchmark.json)。",
        ]
    )
    for scenario in data["scenarios"]:
        repetition = scenario["repetitions"][0]
        lines.extend(
            [
                "",
                f"### {scenario['name']}",
                "",
                f"- 匿名评审选择：**{label(repetition['judge_winner'])}**",
                f"- 硬约束裁决：**{label(repetition['winner'])}**（`{repetition['winner_basis']}`）",
                f"- 评审理由：{repetition['judge_summary']}",
                "",
                "<details>",
                "<summary>查看测试提示</summary>",
                "",
                scenario["writing_prompt"],
                "",
                "</details>",
                "",
                "#### 直接生成",
                "",
                repetition["outputs"]["direct"],
                "",
                f"> 字符数：{repetition['constraint_checks']['direct']['visible_characters']}；自动失败：{failure_text(repetition['automatic_failures']['direct'])}",
                "",
                "#### 训练后",
                "",
                repetition["outputs"]["trained"],
                "",
                f"> 字符数：{repetition['constraint_checks']['trained']['visible_characters']}；自动失败：{failure_text(repetition['automatic_failures']['trained'])}",
            ]
        )

    lines.extend(
        [
            "",
            "## 方法",
            "",
            "1. 每类使用 3 篇授权样本训练，另留 1 篇不参与训练的风格样本给评审。",
            "2. 直接组与训练后组使用相同的 DeepSeek 模型、用户提示、temperature 与 max_tokens。",
            "3. 每类运行 3 次；调用顺序交替，评审前随机映射为 A/B。",
            "4. 评审只看任务、留出样本和匿名稿件；程序另查长度与连续来源重合。",
            "5. 第 1 轮预先固定为公开代表稿，所有轮次均保留，避免只挑胜例。",
            "",
            "## 边界",
            "",
            "- 不使用在世作者姓名宣传“复刻风格”。类似能力用公版作品或用户已授权的自有样本展示。",
            "- DeepSeek 同时充当生成器和匿名评审，结论仍需人工复核；这不是独立人类偏好研究。",
            "- 新闻场景揭示了当前版本的长度控制缺陷，不应隐藏为成功案例。",
            "- 来源与许可逐条记录在 benchmark JSON 中。",
            "",
        ]
    )
    return "\n".join(lines)


def markdown_quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def result_basis(value: str) -> str:
    return {
        "blind_pairwise_judge": "匿名质量裁决",
        "hard_constraint_override": "硬约束覆盖质量偏好",
        "both_failed_hard_constraints": "双方均未通过硬约束",
    }.get(value, value)


def render_github_readme(data: dict[str, Any]) -> str:
    blind = data["overall_blind_preference"]
    qualified = data["overall_qualified_pairwise_results"]
    usage = data["usage"]
    total_pairs = sum(len(scenario["repetitions"]) for scenario in data["scenarios"])
    total_outputs = total_pairs * 2
    rows = []
    for scenario in data["scenarios"]:
        summary = scenario["summary"]
        rows.append(
            "| [{name}](demos/{id}/) | {sources} + 1 留出 | 训练后 {trained}:{direct} 直接 | "
            "训 {q_trained} / 直 {q_direct} / 均失败 {q_tie} | "
            "[直接稿](demos/{id}/outputs/repetition-1-direct.md) · "
            "[训练后稿](demos/{id}/outputs/repetition-1-trained.md) | "
            "[Skill bundle](demos/{id}/skill/) |".format(
                name=scenario["name"],
                id=scenario["id"],
                sources=sum(1 for source in scenario["source_attribution"] if source["role"] == "training"),
                trained=summary["blind_preference"]["trained"],
                direct=summary["blind_preference"]["direct"],
                q_trained=summary["qualified_pairwise_results"]["trained"],
                q_direct=summary["qualified_pairwise_results"]["direct"],
                q_tie=summary["qualified_pairwise_results"]["tie"],
            )
        )
    return "\n".join(
        [
            '<div align="center">',
            "",
            "<h1>Writing Skill Trainer</h1>",
            "<p><strong>让同一个模型从你的样本学习，训练出可复用、可检查的 Writing Skill。</strong></p>",
            "<p>DeepSeek 直接生成 vs. 从样本训练 Skill 后生成</p>",
            "",
            "</div>",
            "",
            "| 训练后盲评偏好 | 直接生成盲评偏好 | 来源重合警报 | DeepSeek 调用 |",
            "|---:|---:|---:|---:|",
            f"| **{blind['trained']}/{total_pairs}** | **{blind['direct']}/{total_pairs}** | **0/{total_outputs}** | **{usage['api_calls']} calls / {usage['tokens']['total_tokens']:,} tokens** |",
            "",
            "> [!IMPORTANT]",
            f"> `{blind['trained']}/{total_pairs}` 是匿名写作质量偏好，不是最终通过率。加入长度、事实和复制检查后，训练后胜 {qualified['trained']}、直接胜 {qualified['direct']}、双方均未通过 {qualified['tie']}。失败结果没有隐藏。",
            "",
            "## 快速查看",
            "",
            "| Demo | 样本 | 匿名偏好 | 硬约束后 | 固定代表稿 | DeepSeek 生成的 Skill |",
            "|---|---:|---:|---:|---|---|",
            *rows,
            "",
            "完整导航：[`demos/`](demos/) · 完整长文：[`SHOWCASE.md`](SHOWCASE.md) · 原始数据：[`results/benchmark.json`](results/benchmark.json) · 本地视觉页：[`index.html`](index.html)",
            "",
            "## 对比的是什么",
            "",
            "```mermaid",
            "flowchart LR",
            '    S[3 篇授权样本] --> T[Writing Skill Trainer] --> K[SKILL.md + style-profile.md] --> G2[同一个 DeepSeek] --> O2[训练后稿件]',
            '    P[同一个用户任务] --> G1[同一个 DeepSeek] --> O1[直接稿件]',
            "    P --> G2",
            "    H[第 4 篇隐藏风格样本] --> J[匿名 A/B 评审]",
            "    O1 --> J",
            "    O2 --> J",
            "```",
            "",
            "两组使用完全相同的用户提示、模型、temperature 和 max_tokens。唯一差异是训练后组加载了 DeepSeek 从样本生成的运行时 Skill bundle。",
            "",
            "## 三个 Demo",
            "",
            "### 1. 《红楼梦》章回体续写",
            "",
            "- 公版文学样本；训练后三轮匿名评审全胜。",
            "- 一轮训练后稿件因超长被硬约束反转，说明风格提升不等于任务必然合格。",
            "- [查看完整 Demo](demos/red-chamber/) · [查看生成 Skill](demos/red-chamber/skill/)",
            "",
            "### 2. 冷峻讽刺小说",
            "",
            "- 使用鲁迅公版作品展示“从细节、叙述距离和反差中学习机制”，不宣传复刻在世作者。",
            "- 训练后匿名偏好 2:1，但长度稳定性仍有问题。",
            "- [查看完整 Demo](demos/restrained-satire/) · [查看生成 Skill](demos/restrained-satire/skill/)",
            "",
            "### 3. 中性科技新闻",
            "",
            "- 中文维基新闻 CC BY 2.5 样本；训练后稿件事实约束优于直接稿。",
            "- 两组均未满足全部硬约束，因此不能包装成成功案例。",
            "- [查看完整 Demo](demos/tech-news/) · [查看生成 Skill](demos/tech-news/skill/)",
            "",
            "## 生成的 Skill Demo",
            "",
            "每个 Demo 都提供可直接浏览的完整目录：",
            "",
            "```text",
            "demos/<scenario>/skill/",
            "├── README.md",
            "├── SKILL.md",
            "└── references/",
            "    └── style-profile.md",
            "```",
            "",
            "这些是 DeepSeek 在该次 benchmark 中实际生成并实际加载的文件，不是事后手写的示意稿。它们属于 benchmark 候选产物，正式使用前仍应人工复核。",
            "",
            "## 实验方法",
            "",
            "1. 每类 3 篇训练样本，另留 1 篇不参与训练的风格样本。",
            "2. 每类保留 3 轮结果，固定第 1 轮作为公开代表稿，不按输赢挑样。",
            "3. 生成顺序交替；评审前随机映射 A/B 身份。",
            "4. DeepSeek 负责训练、两组生成和匿名评审；程序检查长度与连续来源重合。",
            "5. 请求模型为 `deepseek-chat`；API 实际返回 `{}`。".format(", ".join(usage["actual_models"])),
            "",
            "> [!WARNING]",
            "> DeepSeek 同时担任生成器和评审，不等同于独立人类偏好研究。新闻 Demo 暴露了当前版本的长度控制缺陷。对外发布前仍需人工评审。",
            "",
            "## 复现",
            "",
            "Python 3.10+，不依赖第三方包：",
            "",
            "```bash",
            "cp marketing/writing-skill-trainer/.env.example .env.local",
            "# 在被 gitignore 的 .env.local 中填写 DEEPSEEK_API_KEY",
            "",
            "python3 marketing/writing-skill-trainer/prepare_sources.py",
            "python3 marketing/writing-skill-trainer/run_benchmark.py --run-id my-run --repetitions 3",
            "python3 marketing/writing-skill-trainer/render_showcase.py marketing/writing-skill-trainer/runs/my-run",
            "```",
            "",
            "## 来源与边界",
            "",
            "- 《红楼梦》与鲁迅作品：公版。",
            "- 中文维基新闻：CC BY 2.5，逐条链接与哈希见各 Demo 和 benchmark JSON。",
            "- 不使用在世作者姓名宣传“风格复刻”；个人风格案例应使用用户拥有或明确获授权的样本。",
            "",
            f"Run: `{data['run_id']}` · Completed: `{data['completed_at']}`",
            "",
        ]
    )


def render_demos_index(data: dict[str, Any]) -> str:
    rows = []
    for index, scenario in enumerate(data["scenarios"], start=1):
        summary = scenario["summary"]
        rows.append(
            f"| {index} | [{scenario['name']}]({scenario['id']}/) | "
            f"训练后 {summary['blind_preference']['trained']}:{summary['blind_preference']['direct']} 直接 | "
            f"[固定代表稿]({scenario['id']}/outputs/repetition-1-trained.md) | "
            f"[Skill]({scenario['id']}/skill/) |"
        )
    return "\n".join(
        [
            "# Writing Skill Trainer Demos",
            "",
            "[返回总览](../README.md)",
            "",
            "| # | Demo | 匿名偏好 | 训练后代表稿 | 生成的 Skill |",
            "|---:|---|---:|---|---|",
            *rows,
            "",
            "每个目录都包含三轮直接稿、三轮训练后稿、统一测试提示、评分结果、来源许可，以及 benchmark 中实际加载的 Skill bundle。",
            "",
        ]
    )


def render_demo_readme(scenario: dict[str, Any], index: int, total: int) -> str:
    summary = scenario["summary"]
    representative = scenario["repetitions"][0]
    score_names = {
        "task_and_facts": "任务与事实",
        "mechanism_fidelity": "机制保真",
        "voice_and_rhythm": "声音与节奏",
        "originality_and_non_template": "原创与非模板化",
        "reader_effect": "读者效果",
    }
    score_rows = [
        f"| {score_names[dimension]} | {representative['scores']['direct'][dimension]} | {representative['scores']['trained'][dimension]} |"
        for dimension in score_names
    ]
    run_rows = []
    for repetition in scenario["repetitions"]:
        number = repetition["repetition"]
        run_rows.append(
            f"| {number} | [直接稿](outputs/repetition-{number}-direct.md) | "
            f"[训练后稿](outputs/repetition-{number}-trained.md) | "
            f"{label(repetition['judge_winner'])} | {label(repetition['winner'])} | "
            f"{result_basis(repetition['winner_basis'])} |"
        )
    source_rows = [
        f"| [{source['title']}]({source['url']}) | {source['role']} | {source['license']} | `{source['sha256'][:12]}` |"
        for source in scenario["source_attribution"]
    ]
    report = scenario["training_report"]

    def report_items(values: list[Any] | None) -> list[str]:
        items = []
        for value in values or []:
            if isinstance(value, dict):
                sample = value.get("sample_id", "")
                evidence = value.get("evidence", json.dumps(value, ensure_ascii=False))
                items.append(f"- **{sample}**：{evidence}" if sample else f"- {evidence}")
            else:
                items.append(f"- {value}")
        return items or ["- 无"]

    direct_check = representative["constraint_checks"]["direct"]
    trained_check = representative["constraint_checks"]["trained"]
    return "\n".join(
        [
            "[返回 Demo 总览](../README.md) · [返回项目总览](../../README.md)",
            "",
            f"# Demo {index + 1}/{total}：{scenario['name']}",
            "",
            f"> {scenario['target']}",
            "",
            "## 结果摘要",
            "",
            "| 指标 | 结果 |",
            "|---|---|",
            f"| 三轮匿名偏好 | 训练后 {summary['blind_preference']['trained']} : {summary['blind_preference']['direct']} 直接 |",
            f"| 硬约束后 | 训练后胜 {summary['qualified_pairwise_results']['trained']} / 直接胜 {summary['qualified_pairwise_results']['direct']} / 均失败 {summary['qualified_pairwise_results']['tie']} |",
            f"| 平均机制保真 | 训练后 {summary['mean_scores']['trained']['mechanism_fidelity']:.2f} / 直接 {summary['mean_scores']['direct']['mechanism_fidelity']:.2f} |",
            f"| 来源复制警报 | 训练后 {summary['copy_flags']['trained']} / 直接 {summary['copy_flags']['direct']} |",
            "",
            "## 固定代表轮：Repetition 1",
            "",
            "代表轮在评审前固定，不按结果挑选。",
            "",
            "| 指标 | 直接生成 | 训练后 |",
            "|---|---:|---:|",
            f"| 字符数 | {direct_check['visible_characters']} | {trained_check['visible_characters']} |",
            f"| 硬约束 | {'通过' if direct_check['eligible'] else '失败'} | {'通过' if trained_check['eligible'] else '失败'} |",
            f"| 最长来源重合 | {representative['overlap']['direct']['characters']} 字 | {representative['overlap']['trained']['characters']} 字 |",
            f"| 平均评分 | {score_average(representative['scores']['direct']):.2f} | {score_average(representative['scores']['trained']):.2f} |",
            "",
            f"- 匿名评审偏好：**{label(representative['judge_winner'])}**",
            f"- 硬约束后裁决：**{label(representative['winner'])}**",
            f"- 理由：{representative['judge_summary']}",
            "",
            "[查看直接生成全文](outputs/repetition-1-direct.md) · [查看训练后全文](outputs/repetition-1-trained.md) · [查看统一测试提示](prompt.md)",
            "",
            "### 代表轮评分",
            "",
            "| 维度 | 直接生成 | 训练后 |",
            "|---|---:|---:|",
            *score_rows,
            "",
            "## 全部三轮",
            "",
            "| 轮次 | 直接稿 | 训练后稿 | 匿名偏好 | 硬约束后 | 裁决依据 |",
            "|---:|---|---|---|---|---|",
            *run_rows,
            "",
            "## DeepSeek 训练出的 Skill Demo",
            "",
            "- [浏览完整 Skill bundle](skill/)",
            "- [SKILL.md](skill/SKILL.md)",
            "- [style-profile.md](skill/references/style-profile.md)",
            "",
            "> [!NOTE]",
            "> 这里提供的是 benchmark 中实际加载的候选 Skill，不是为展示重新手写的版本。正式使用前仍需人工复核。",
            "",
            "### 训练证据摘要",
            "",
            *report_items(report.get("evidence_summary")),
            "",
            "### 暂定规则",
            "",
            *report_items(report.get("provisional_rules")),
            "",
            "### 主动排除的表层特征",
            "",
            *report_items(report.get("excluded_surface_features")),
            "",
            "## 来源与许可",
            "",
            "| 来源 | 角色 | 许可 | SHA-256 |",
            "|---|---|---|---|",
            *source_rows,
            "",
            "完整机器可读记录：[`../../results/benchmark.json`](../../results/benchmark.json)",
            "",
        ]
    )


def render_output_page(scenario: dict[str, Any], repetition: dict[str, Any], condition: str) -> str:
    number = repetition["repetition"]
    checks = repetition["constraint_checks"][condition]
    failures = repetition["automatic_failures"][condition]
    score_names = {
        "task_and_facts": "任务与事实",
        "mechanism_fidelity": "机制保真",
        "voice_and_rhythm": "声音与节奏",
        "originality_and_non_template": "原创与非模板化",
        "reader_effect": "读者效果",
    }
    score_rows = [
        f"| {name} | {repetition['scores'][condition][dimension]} |"
        for dimension, name in score_names.items()
    ]
    return "\n".join(
        [
            f"[返回 {scenario['name']}](../README.md)",
            "",
            f"# {label(condition)} · Repetition {number}",
            "",
            "| 元数据 | 值 |",
            "|---|---|",
            f"| 条件 | `{condition}` |",
            f"| API 模型 | `{repetition['models'][condition]}` |",
            f"| 可见字符数 | {checks['visible_characters']} |",
            f"| 要求范围 | {checks['required_range']['min']}—{checks['required_range']['max']} |",
            f"| 硬约束 | {'通过' if checks['eligible'] else '失败'} |",
            f"| 最长来源重合 | {repetition['overlap'][condition]['characters']} 字 |",
            f"| 匿名评审偏好 | {label(repetition['judge_winner'])} |",
            f"| 最终裁决 | {label(repetition['winner'])} |",
            "",
            "> [!WARNING]" if failures else "> [!NOTE]",
            f"> 自动失败：{failure_text(failures)}" if failures else "> 未触发自动失败项。",
            "",
            "## 评分",
            "",
            "| 维度 | 分数 |",
            "|---|---:|",
            *score_rows,
            "",
            "## 正文",
            "",
            markdown_quote(repetition["outputs"][condition]),
            "",
            "## 成对评审理由",
            "",
            repetition["judge_summary"],
            "",
        ]
    )


def render_skill_readme(scenario: dict[str, Any], data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"[返回 {scenario['name']} Demo](../README.md)",
            "",
            f"# Generated Skill Demo：{scenario['name']}",
            "",
            "> 这是 DeepSeek 在 benchmark 中从 3 篇样本实际生成、并在训练后组实际加载的 Skill bundle。",
            "",
            "## 文件",
            "",
            "```text",
            "skill/",
            "├── README.md",
            "├── SKILL.md",
            "└── references/",
            "    └── style-profile.md",
            "```",
            "",
            "- [`SKILL.md`](SKILL.md)：运行时流程、事实边界和自检。",
            "- [`references/style-profile.md`](references/style-profile.md)：从样本提炼的机制、语气旋钮与反模式。",
            "",
            "## 使用方式",
            "",
            "将整个 `skill/` 目录复制到你的 Agent 支持的 Skill 目录，再按平台要求加载。不要只复制 `SKILL.md`，因为运行时会读取 `references/style-profile.md`。",
            "",
            "> [!CAUTION]",
            "> 这是实验候选版本，不代表已达到生产发布标准。请先检查触发描述、版权边界、事实约束和输出长度。",
            "",
            f"Run: `{data['run_id']}` · requested model: `{data['requested_model']}` · actual model: `{', '.join(data['usage']['actual_models'])}`",
            "",
        ]
    )


def condition_card(condition: str, repetition: dict[str, Any]) -> str:
    checks = repetition["constraint_checks"][condition]
    failures = repetition["automatic_failures"][condition]
    avg = score_average(repetition["scores"][condition])
    status = "pass" if checks["eligible"] else "fail"
    return f"""
    <article class="output-card {status}">
      <header>
        <div><span class="eyebrow">{escape(label(condition))}</span><h4>{escape(condition)}</h4></div>
        <div class="score">{avg:.1f}<small>/10</small></div>
      </header>
      <div class="checks">
        <span>{checks['visible_characters']} 字</span>
        <span class="{status}">{'通过硬约束' if checks['eligible'] else '未通过硬约束'}</span>
        <span>最长来源重合 {repetition['overlap'][condition]['characters']} 字</span>
      </div>
      {f'<div class="failure"><strong>自动失败：</strong>{escape(failure_text(failures))}</div>' if failures else ''}
      <div class="prose">{escape(repetition['outputs'][condition])}</div>
    </article>
    """


def scenario_section(scenario: dict[str, Any], index: int) -> str:
    summary = scenario["summary"]
    representative = scenario["repetitions"][0]
    rows = []
    for repetition in scenario["repetitions"]:
        direct = repetition["constraint_checks"]["direct"]
        trained = repetition["constraint_checks"]["trained"]
        rows.append(
            f"""
            <tr>
              <td>{repetition['repetition']}</td>
              <td>{escape(label(repetition['judge_winner']))}</td>
              <td>{escape(label(repetition['winner']))}</td>
              <td>{trained['visible_characters']} / {direct['visible_characters']}</td>
              <td>{'通过' if trained['eligible'] else '失败'} / {'通过' if direct['eligible'] else '失败'}</td>
              <td>{escape(repetition['judge_summary'])}</td>
            </tr>
            """
        )
    sources = "".join(
        f'<li><a href="{escape(source["url"])}">{escape(source["title"])}</a> · {escape(source["role"])} · {escape(source["license"])}</li>'
        for source in scenario["source_attribution"]
    )
    return f"""
    <section class="scenario" id="{escape(scenario['id'])}">
      <div class="scenario-head">
        <div><span class="eyebrow">案例 {index + 1} · {escape(scenario['category'])}</span><h2>{escape(scenario['name'])}</h2><p>{escape(scenario['target'])}</p></div>
        <div class="mini-stats">
          <div><strong>{summary['blind_preference']['trained']}:{summary['blind_preference']['direct']}</strong><span>训练后 : 直接<br>匿名偏好</span></div>
          <div><strong>{summary['mean_scores']['trained']['mechanism_fidelity']:.2f}</strong><span>训练后<br>机制分</span></div>
          <div><strong>{summary['mean_scores']['direct']['mechanism_fidelity']:.2f}</strong><span>直接<br>机制分</span></div>
        </div>
      </div>

      <details class="prompt"><summary>查看完全相同的用户提示</summary><pre>{escape(scenario['writing_prompt'])}</pre></details>

      <div class="verdict"><strong>固定代表轮 #1：</strong>匿名评审偏好 {escape(label(representative['judge_winner']))}。{escape(representative['judge_summary'])}</div>
      <div class="outputs">
        {condition_card('direct', representative)}
        {condition_card('trained', representative)}
      </div>

      <details><summary>查看全部三轮结果</summary>
        <div class="table-wrap"><table><thead><tr><th>轮次</th><th>盲评偏好</th><th>硬约束后</th><th>字数 训/直</th><th>合格 训/直</th><th>理由</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
      </details>
      <details><summary>查看 DeepSeek 训练出的 Skill</summary><div class="artifact-grid"><pre>{escape(scenario['trained_skill'])}</pre><pre>{escape(scenario['trained_style_profile'])}</pre></div></details>
      <details><summary>来源与许可</summary><ul>{sources}</ul></details>
    </section>
    """


def render_html(data: dict[str, Any]) -> str:
    blind = data["overall_blind_preference"]
    qualified = data["overall_qualified_pairwise_results"]
    usage = data["usage"]
    scenario_html = "".join(scenario_section(scenario, index) for index, scenario in enumerate(data["scenarios"]))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Writing Skill Trainer · DeepSeek 实测</title>
<style>
:root{{--ink:#17221c;--muted:#68736d;--paper:#f5f2e9;--card:#fffdf7;--line:#d9d5c9;--green:#165c3a;--lime:#d9f26a;--red:#8e3f30;--shadow:0 18px 60px rgba(28,45,35,.09)}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;color:var(--ink);background:var(--paper);font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans CJK SC",sans-serif;line-height:1.7}}
a{{color:var(--green)}} .wrap{{max-width:1180px;margin:auto;padding:0 24px}} .hero{{padding:88px 0 64px;background:var(--ink);color:#fff;overflow:hidden;position:relative}} .hero:after{{content:"";position:absolute;width:460px;height:460px;border-radius:50%;background:var(--lime);filter:blur(120px);opacity:.18;right:-100px;top:-170px}} .kicker,.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:750;color:var(--green)}} .hero .kicker{{color:var(--lime)}} h1{{font-size:clamp(42px,7vw,82px);line-height:1.03;letter-spacing:-.05em;margin:18px 0 24px;max-width:940px}} .hero-copy{{font-size:20px;color:#d7ded9;max-width:780px}} .hero-copy strong{{color:#fff}} .stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:48px;position:relative;z-index:1}} .stat{{border:1px solid #425048;border-radius:18px;padding:20px;background:#ffffff08}} .stat strong{{font-size:34px;display:block;color:var(--lime)}} .stat span{{font-size:13px;color:#bac6bf}} .disclosure{{margin-top:22px;color:#9faaa4;font-size:13px;max-width:920px}}
main{{padding:64px 0 100px}} .intro{{display:grid;grid-template-columns:1.3fr .7fr;gap:24px;margin-bottom:70px}} .panel{{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:28px;box-shadow:var(--shadow)}} .panel h2{{font-size:30px;margin:0 0 14px}} .panel ul{{padding-left:20px}} .warning{{background:#fff4d7;border-color:#e7cf8f}} .scenario{{padding:60px 0;border-top:1px solid var(--line)}} .scenario-head{{display:grid;grid-template-columns:1.3fr .7fr;gap:36px;align-items:end}} h2{{font-size:42px;line-height:1.15;letter-spacing:-.03em;margin:8px 0 12px}} .scenario-head p{{color:var(--muted);font-size:17px;max-width:720px}} .mini-stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}} .mini-stats div{{background:var(--card);border:1px solid var(--line);padding:15px;border-radius:14px}} .mini-stats strong{{font-size:24px;display:block}} .mini-stats span{{color:var(--muted);font-size:11px;line-height:1.35;display:block}} details{{margin:18px 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:0 18px}} summary{{cursor:pointer;font-weight:700;padding:14px 0}} pre{{white-space:pre-wrap;word-break:break-word;font:13px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;background:#17221c;color:#dfe9e2;border-radius:12px;padding:18px;max-height:620px;overflow:auto}} .verdict{{margin:28px 0 16px;border-left:4px solid var(--green);background:#eaf4ed;padding:15px 18px;border-radius:0 12px 12px 0}} .outputs{{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}} .output-card{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:var(--shadow)}} .output-card.fail{{border-color:#d8afa7}} .output-card header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:12px}} .output-card h4{{margin:0;font-size:22px}} .score{{font-size:26px;font-weight:800}} .score small{{font-size:12px;color:var(--muted)}} .checks{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}} .checks span{{font-size:11px;padding:4px 8px;background:#edf0ed;border-radius:100px}} .checks .pass{{background:#dff0e5;color:var(--green)}} .checks .fail{{background:#f4dfda;color:var(--red)}} .failure{{font-size:12px;background:#fff0ec;color:var(--red);padding:9px;border-radius:8px;margin-bottom:12px}} .prose{{white-space:pre-wrap;font-family:ui-serif,"Songti SC",STSong,serif;font-size:16px;line-height:1.9;max-height:720px;overflow:auto;padding-right:8px}} .table-wrap{{overflow:auto;margin-bottom:18px}} table{{border-collapse:collapse;width:100%;font-size:12px}} th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}} .artifact-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding-bottom:18px}} footer{{padding:40px 0 70px;color:var(--muted);border-top:1px solid var(--line)}} code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
@media(max-width:820px){{.stats{{grid-template-columns:1fr 1fr}}.intro,.scenario-head,.outputs,.artifact-grid{{grid-template-columns:1fr}}h2{{font-size:34px}}.mini-stats{{margin-top:10px}}}}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <div class="kicker">DeepSeek-only reproducible benchmark</div>
  <h1>不是让模型猜你的风格。<br>是训练出你的 Writing Skill。</h1>
  <p class="hero-copy">同一个 DeepSeek、同一个任务：<strong>直接生成</strong>对比<strong>从样本训练 Skill 后生成</strong>。三类写作、九轮匿名 A/B，完整失败也公开。</p>
  <div class="stats">
    <div class="stat"><strong>{blind['trained']}/9</strong><span>匿名评审偏好训练后稿件</span></div>
    <div class="stat"><strong>{blind['direct']}/9</strong><span>匿名评审偏好直接稿件</span></div>
    <div class="stat"><strong>0/18</strong><span>触发连续 30 字来源重合</span></div>
    <div class="stat"><strong>{usage['tokens']['total_tokens']:,}</strong><span>公开记录的 DeepSeek tokens</span></div>
  </div>
  <p class="disclosure">7/9 是匿名质量偏好，不是通过率。严格硬约束后：训练后胜 {qualified['trained']}、直接胜 {qualified['direct']}、双方均未通过 {qualified['tie']}。请求模型为 deepseek-chat，API 实际返回 {escape(', '.join(usage['actual_models']))}。</p>
</div></header>
<main><div class="wrap">
  <section class="intro">
    <div class="panel"><span class="eyebrow">What changed</span><h2>模型没变，写作系统变了</h2><p>直接组只收到自然语言任务；训练后组额外加载 DeepSeek 从 3 篇样本生成的运行时 <code>SKILL.md</code> 与 <code>style-profile.md</code>。第 4 篇同类样本不参与训练，只给匿名评审判断机制迁移。</p><ul><li>每类三轮，全部保留</li><li>调用顺序交替，A/B 身份随机</li><li>文学样本均为公版；新闻样本为 CC BY 2.5</li><li>程序检查长度和来源重合，评审检查事实与风格</li></ul></div>
    <div class="panel warning"><span class="eyebrow">What did not work</span><h2>风格提升，不等于成品合格</h2><p>新闻训练后稿件没有补造“分析人士”观点，但三轮都低于长度要求；直接组也因长度或补造事实失败。文学场景中，训练后稿件也有超长。当前版本仍需加强长度规划。</p></div>
  </section>
  {scenario_html}
  <section class="scenario"><span class="eyebrow">Methodology</span><h2>可复现，而不是截图营销</h2><div class="panel"><ol><li>3 篇训练样本 + 1 篇隐藏风格留出样本。</li><li>DeepSeek 读取 Writing Skill Trainer，生成下游 Skill bundle。</li><li>同一用户提示与参数分别直接生成、加载 Skill 生成。</li><li>输出随机映射 A/B，由 DeepSeek 匿名成对评审。</li><li>程序检查精确长度与连续文本重合；自动失败优先于质量偏好。</li></ol><p>限制：生成器和评审来自同一模型家族，结果仍需人工复核。完整 JSON、输出、评分、来源哈希和许可均随仓库提供。</p></div></section>
</div></main>
<footer><div class="wrap">Writing Skill Trainer · run {escape(data['run_id'])} · {escape(data['completed_at'])}</div></footer>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    benchmark_path = run_dir / "benchmark.json"
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))

    public_results = ROOT / "results"
    if public_results.exists():
        shutil.rmtree(public_results)
    public_results.mkdir(parents=True)
    shutil.copy2(benchmark_path, public_results / "benchmark.json")

    demos_root = ROOT / "demos"
    if demos_root.exists():
        shutil.rmtree(demos_root)
    demos_root.mkdir(parents=True)
    (demos_root / "README.md").write_text(render_demos_index(data), encoding="utf-8")

    total_scenarios = len(data["scenarios"])
    for index, scenario in enumerate(data["scenarios"]):
        result_skill = public_results / "trained-skills" / scenario["id"]
        result_skill.mkdir(parents=True, exist_ok=True)
        (result_skill / "SKILL.md").write_text(
            scenario["trained_skill"].rstrip() + "\n", encoding="utf-8"
        )
        result_references = result_skill / "references"
        result_references.mkdir()
        (result_references / "style-profile.md").write_text(
            scenario["trained_style_profile"].rstrip() + "\n", encoding="utf-8"
        )

        demo_dir = demos_root / scenario["id"]
        outputs_dir = demo_dir / "outputs"
        skill_dir = demo_dir / "skill"
        skill_references = skill_dir / "references"
        outputs_dir.mkdir(parents=True)
        skill_references.mkdir(parents=True)
        (demo_dir / "README.md").write_text(
            render_demo_readme(scenario, index, total_scenarios), encoding="utf-8"
        )
        (demo_dir / "prompt.md").write_text(
            "\n".join(
                [
                    f"[返回 {scenario['name']}](README.md)",
                    "",
                    f"# 统一测试提示：{scenario['name']}",
                    "",
                    "直接组与训练后组收到完全相同的用户提示：",
                    "",
                    markdown_quote(scenario["writing_prompt"]),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        for repetition in scenario["repetitions"]:
            for condition in ("direct", "trained"):
                output_path = outputs_dir / f"repetition-{repetition['repetition']}-{condition}.md"
                output_path.write_text(
                    render_output_page(scenario, repetition, condition), encoding="utf-8"
                )
        (skill_dir / "README.md").write_text(
            render_skill_readme(scenario, data), encoding="utf-8"
        )
        (skill_dir / "SKILL.md").write_text(
            scenario["trained_skill"].rstrip() + "\n", encoding="utf-8"
        )
        (skill_references / "style-profile.md").write_text(
            scenario["trained_style_profile"].rstrip() + "\n", encoding="utf-8"
        )

    (ROOT / "README.md").write_text(render_github_readme(data), encoding="utf-8")
    (ROOT / "SHOWCASE.md").write_text(render_markdown(data), encoding="utf-8")
    html_output = "\n".join(line.rstrip() for line in render_html(data).splitlines()) + "\n"
    (ROOT / "index.html").write_text(html_output, encoding="utf-8")
    print(f"Published {ROOT / 'README.md'}")
    print(f"Published {demos_root}")
    print(f"Published {ROOT / 'SHOWCASE.md'}")
    print(f"Published {ROOT / 'index.html'}")
    print(f"Published {public_results / 'benchmark.json'}")


if __name__ == "__main__":
    main()
