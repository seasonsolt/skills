#!/usr/bin/env python3
"""Run a reproducible DeepSeek-only A/B benchmark for Writing Skill Trainer."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import random
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DEFAULT_SCENARIOS = ROOT / "data" / "scenarios.json"
TRAINER_SKILL = REPO_ROOT / "skills" / "writing-skill-trainer" / "SKILL.md"
API_URL = "https://api.deepseek.com/chat/completions"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object from DeepSeek")
    return value


def normalize_skill_frontmatter(skill_md: str) -> tuple[str, list[str]]:
    """Repair indentation of top-level YAML keys without changing writing rules."""
    lines = skill_md.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return skill_md, []
    repairs: list[str] = []
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            break
        stripped = lines[index].lstrip()
        if stripped.startswith(("name:", "description:", "compatibility:")) and stripped != lines[index]:
            repairs.append(f"frontmatter line {index + 1}: removed accidental leading whitespace")
            lines[index] = stripped
    return "\n".join(lines), repairs


class DeepSeekClient:
    def __init__(self, api_key: str, requested_model: str) -> None:
        self.api_key = api_key
        self.requested_model = requested_model

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_output: bool = False,
        attempts: int = 6,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.requested_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "seasonsolt-writing-skill-showcase/1.0",
            },
            method="POST",
        )
        for attempt in range(attempts):
            try:
                started = time.monotonic()
                with urllib.request.urlopen(request, timeout=300) as response:
                    raw = json.load(response)
                elapsed = round(time.monotonic() - started, 3)
                choice = raw["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise RuntimeError("DeepSeek response was truncated at max_tokens")
                return {
                    "api_response_id": raw.get("id"),
                    "created": raw.get("created"),
                    "requested_model": self.requested_model,
                    "actual_model": raw.get("model"),
                    "finish_reason": choice.get("finish_reason"),
                    "content": choice["message"].get("content", ""),
                    "usage": raw.get("usage", {}),
                    "elapsed_seconds": elapsed,
                    "request": {
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "response_format": payload.get("response_format"),
                    },
                }
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", "replace")[:1000]
                if attempt == attempts - 1 or error.code not in {408, 409, 429, 500, 502, 503, 504}:
                    raise RuntimeError(f"DeepSeek HTTP {error.code}: {body}") from error
                retry_after = error.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 30)
                time.sleep(delay)
            except (OSError, TimeoutError) as error:
                if attempt == attempts - 1:
                    raise RuntimeError(f"DeepSeek request failed: {error}") from error
                time.sleep(min(2**attempt, 30))
        raise RuntimeError("unreachable")


def call_or_load(
    client: DeepSeekClient,
    path: Path,
    *,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    json_output: bool,
) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    result = client.complete(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_output=json_output,
    )
    write_json(path, result)
    usage = result.get("usage", {})
    print(
        f"  saved {path.relative_to(path.parents[3])} "
        f"model={result.get('actual_model')} tokens={usage.get('total_tokens', '?')}"
    )
    return result


def training_messages(trainer_skill: str, scenario: dict[str, Any]) -> list[dict[str, str]]:
    sources = []
    for index, source in enumerate(scenario["training_sources"], start=1):
        sources.append(
            "\n".join(
                [
                    f"<sample id=\"S{index}\">",
                    f"标题：{source['title']}",
                    f"授权：{source['license']}",
                    f"来源：{source['url']}",
                    source["text"],
                    "</sample>",
                ]
            )
        )
    user_prompt = f"""
下面是已安装的 Writing Skill Trainer。请把它作为执行规范，而不是作为待评论的文章。

<installed_skill>
{trainer_skill}
</installed_skill>

<training_task>
场景：{scenario['name']}
目标：{scenario['target']}
样本均已明确授权，可用于抽象写作机制。

{"\n\n".join(sources)}

执行 Phase 1 与 Phase 2：从重复证据中训练出一个最小、可执行的候选 Writing Skill。外部 benchmark harness 将负责 baseline、盲评、留出回归和 keep/revert，因此不要声称已经验证。候选 Skill 将只用于隔离测试。

约束：
1. 只学习结构、叙述决策、语气控制、证据使用和适用边界，不复制样本的连续表达。
2. 不把样本里的专名、事件、数字或句子写成通用模板。
3. 生成的是供写作任务直接加载的运行时 Skill，不是另一个训练器；不要把训练、盲评或进化流程挤进运行时正文。
4. skill_md 必须要求写作前读取同目录的 references/style-profile.md；不得引用本次没有返回的其他文件。
5. YAML frontmatter 的 name 和 description 必须顶格、语法有效。SKILL.md 正文尽量控制在 120 行以内。
6. style_profile_md 要把跨样本机制写成可执行的条件规则、决策顺序、语气旋钮、反模式和最终自检；每条核心规则标注 sample id 证据，但不得收录可复用原句。
7. 返回一个 JSON 对象，字段严格为：
   - skill_md：完整候选 SKILL.md 字符串（含 YAML frontmatter）
   - style_profile_md：完整 references/style-profile.md 字符串
   - evidence_summary：3—8 条带 sample id 的机制证据
   - provisional_rules：仍需跨任务验证的规则数组
   - excluded_surface_features：主动排除的表层特征数组
</training_task>
""".strip()
    return [
        {
            "role": "system",
            "content": "你是 DeepSeek，正在执行一个已安装的 Agent Skill。严格按规范训练候选写作 Skill。只返回有效 JSON，不要输出 Markdown 围栏或额外说明。",
        },
        {"role": "user", "content": user_prompt},
    ]


def generation_messages(scenario: dict[str, Any], custom_skill: str | None) -> list[dict[str, str]]:
    base = (
        "你是 DeepSeek 写作模型。严格遵守用户给出的事实、长度、格式与版权边界；"
        "不得补造未提供的引语、数字或重大情节。非虚构任务中，不得自行添加看似合理的"
        "背景、影响判断、第三方观点或未来计划。交付前复核长度与全部硬约束。"
        "只输出最终成稿，不解释过程。"
    )
    if custom_skill:
        base += (
            "\n\n下面加载了一个从样本训练出的候选 Writing Skill。"
            "先按其中的决策流程完成任务；若它与用户事实冲突，以用户事实和安全边界为准。"
            f"\n\n<custom_writing_skill>\n{custom_skill}\n</custom_writing_skill>"
        )
    return [
        {"role": "system", "content": base},
        {"role": "user", "content": scenario["writing_prompt"]},
    ]


def judge_messages(
    scenario: dict[str, Any], output_a: str, output_b: str
) -> list[dict[str, str]]:
    criteria = "\n".join(f"- {item}" for item in scenario["evaluation_criteria"])
    holdout = scenario["style_holdout"]
    prompt = f"""
你要对两个匿名输出做成对盲评。A/B 由程序随机放置；不要猜测哪个加载过 Skill，也不要偏爱更长、古词更多或格式更复杂的稿件。

<task>
{scenario['writing_prompt']}
</task>

<style_holdout>
这是未参与候选 Skill 训练的同类风格留出样本，仅用于判断底层机制，不要求字面相似。
标题：{holdout['title']}
授权：{holdout['license']}
{holdout['text']}
</style_holdout>

<criteria>
{criteria}
</criteria>

<output_A>
{output_a}
</output_A>

<output_B>
{output_b}
</output_B>

先做硬约束审计，再比较写作机制与读者效果。非虚构任务中，逐项检查每个来源、背景、影响判断和未来计划是否出现在事实包；例如凭空出现“分析人士指出”、推测性影响或未提供的后续行动，必须写入 automatic_failures。小说允许补足日常动作与场景，但不得违反用户给定情节或新增重大设定。返回有效 JSON，结构严格为：
{{
  "winner": "A" | "B" | "tie",
  "confidence": 0.0到1.0,
  "scores": {{
    "A": {{"task_and_facts": 1到10, "mechanism_fidelity": 1到10, "voice_and_rhythm": 1到10, "originality_and_non_template": 1到10, "reader_effect": 1到10}},
    "B": {{"task_and_facts": 1到10, "mechanism_fidelity": 1到10, "voice_and_rhythm": 1到10, "originality_and_non_template": 1到10, "reader_effect": 1到10}}
  }},
  "criterion_findings": [{{"criterion": "...", "preferred": "A|B|tie", "evidence": "引用或转述两稿中的具体证据"}}],
  "automatic_failures": {{"A": [], "B": []}},
  "summary": "不超过180字的裁决理由"
}}
""".strip()
    return [
        {
            "role": "system",
            "content": "你是严格的中文写作盲评员。身份未知时只依据任务、留出样本和稿件裁决。只返回有效 JSON。",
        },
        {"role": "user", "content": prompt},
    ]


def visible_character_count(text: str) -> int:
    return sum(1 for character in text if not character.isspace())


def normalized_for_overlap(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", text)
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    )


def longest_source_match(output: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_output = normalized_for_overlap(output)
    best = {"characters": 0, "source": None, "excerpt": ""}
    for source in sources:
        normalized_source = normalized_for_overlap(source["text"])
        match = difflib.SequenceMatcher(
            None, normalized_output, normalized_source, autojunk=False
        ).find_longest_match()
        if match.size > best["characters"]:
            best = {
                "characters": match.size,
                "source": source["title"],
                "excerpt": normalized_output[match.a : match.a + match.size],
            }
    best["flagged"] = best["characters"] >= 30
    return best


def validate_judge(value: dict[str, Any]) -> None:
    if value.get("winner") not in {"A", "B", "tie"}:
        raise ValueError(f"Invalid judge winner: {value.get('winner')!r}")
    for label in ("A", "B"):
        scores = value.get("scores", {}).get(label, {})
        for dimension in (
            "task_and_facts",
            "mechanism_fidelity",
            "voice_and_rhythm",
            "originality_and_non_template",
            "reader_effect",
        ):
            score = scores.get(dimension)
            if not isinstance(score, (int, float)) or not 1 <= score <= 10:
                raise ValueError(f"Invalid {label}.{dimension} score: {score!r}")


def scenario_summary(repetitions: list[dict[str, Any]]) -> dict[str, Any]:
    win_counts = {"trained": 0, "direct": 0, "tie": 0}
    blind_preference = {"trained": 0, "direct": 0, "tie": 0}
    eligible_outputs = {"trained": 0, "direct": 0}
    dimensions = [
        "task_and_facts",
        "mechanism_fidelity",
        "voice_and_rhythm",
        "originality_and_non_template",
        "reader_effect",
    ]
    score_values = {
        condition: {dimension: [] for dimension in dimensions}
        for condition in ("direct", "trained")
    }
    for repetition in repetitions:
        win_counts[repetition["winner"]] += 1
        blind_preference[repetition["judge_winner"]] += 1
        for condition in ("direct", "trained"):
            if repetition["constraint_checks"][condition]["eligible"]:
                eligible_outputs[condition] += 1
            for dimension in dimensions:
                score_values[condition][dimension].append(
                    repetition["scores"][condition][dimension]
                )
    return {
        "qualified_pairwise_results": win_counts,
        "blind_preference": blind_preference,
        "eligible_outputs": eligible_outputs,
        "mean_scores": {
            condition: {
                dimension: round(mean(values), 2)
                for dimension, values in condition_scores.items()
            }
            for condition, condition_scores in score_values.items()
        },
        "copy_flags": {
            condition: sum(
                1 for item in repetitions if item["overlap"][condition]["flagged"]
            )
            for condition in ("direct", "trained")
        },
    }


def collect_usage(run_dir: Path) -> dict[str, Any]:
    totals: dict[str, int] = {}
    actual_models: set[str] = set()
    calls = 0
    for path in run_dir.rglob("*.json"):
        if path.name == "benchmark.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or "api_response_id" not in payload:
            continue
        calls += 1
        if payload.get("actual_model"):
            actual_models.add(payload["actual_model"])
        for key, value in payload.get("usage", {}).items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    return {"api_calls": calls, "actual_models": sorted(actual_models), "tokens": totals}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--only", action="append", help="Run only this scenario id; repeatable")
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env.local")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    load_dotenv(args.env_file)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set; export it or put it in ignored .env.local")

    dataset = json.loads(args.scenarios.read_text(encoding="utf-8"))
    trainer_skill = TRAINER_SKILL.read_text(encoding="utf-8")
    client = DeepSeekClient(api_key, args.model)
    run_dir = ROOT / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    benchmark_scenarios = []

    selected_scenarios = [
        scenario
        for scenario in dataset["scenarios"]
        if not args.only or scenario["id"] in set(args.only)
    ]
    if not selected_scenarios:
        raise SystemExit(f"No matching scenarios for --only: {args.only}")

    for scenario in selected_scenarios:
        scenario_dir = run_dir / scenario["id"]
        print(f"[{scenario['id']}] train candidate skill")
        train_messages = training_messages(trainer_skill, scenario)
        training_call = call_or_load(
            client,
            scenario_dir / "training-call.json",
            messages=train_messages,
            temperature=0.2,
            max_tokens=5000,
            json_output=True,
        )
        training_value = parse_json_content(training_call["content"])
        custom_skill = training_value.get("skill_md")
        style_profile = training_value.get("style_profile_md")
        frontmatter_repairs: list[str] = []
        if isinstance(custom_skill, str):
            custom_skill, frontmatter_repairs = normalize_skill_frontmatter(custom_skill)
            training_value["skill_md"] = custom_skill
            training_value["deterministic_repairs"] = frontmatter_repairs
        if (
            not isinstance(custom_skill, str)
            or not re.search(r"(?m)^name:\s*[-a-z0-9]+\s*$", custom_skill)
            or not re.search(r"(?m)^description:\s*(?:>|>-)?.*$", custom_skill)
        ):
            raise ValueError(f"{scenario['id']}: DeepSeek did not return valid SKILL.md frontmatter")
        if not isinstance(style_profile, str) or len(style_profile.strip()) < 200:
            raise ValueError(f"{scenario['id']}: DeepSeek did not return a useful style_profile_md")
        (scenario_dir / "trained-SKILL.md").write_text(custom_skill.rstrip() + "\n", encoding="utf-8")
        (scenario_dir / "trained-style-profile.md").write_text(style_profile.rstrip() + "\n", encoding="utf-8")
        write_json(scenario_dir / "training-report.json", training_value)
        runtime_bundle = (
            custom_skill.rstrip()
            + "\n\n<references/style-profile.md>\n"
            + style_profile.rstrip()
            + "\n</references/style-profile.md>"
        )

        repetition_results = []
        for repetition in range(1, args.repetitions + 1):
            print(f"[{scenario['id']}] repetition {repetition}/{args.repetitions}")
            repetition_dir = scenario_dir / f"repetition-{repetition}"
            conditions = ["direct", "trained"]
            if repetition % 2 == 0:
                conditions.reverse()
            calls: dict[str, dict[str, Any]] = {}
            for condition in conditions:
                calls[condition] = call_or_load(
                    client,
                    repetition_dir / f"{condition}.json",
                    messages=generation_messages(
                        scenario, runtime_bundle if condition == "trained" else None
                    ),
                    temperature=scenario["generation"]["temperature"],
                    max_tokens=scenario["generation"]["max_tokens"],
                    json_output=False,
                )

            direct_text = calls["direct"]["content"].strip()
            trained_text = calls["trained"]["content"].strip()
            randomizer = random.Random(f"{args.run_id}:{scenario['id']}:{repetition}")
            direct_label = "A" if randomizer.randrange(2) == 0 else "B"
            trained_label = "B" if direct_label == "A" else "A"
            output_a = direct_text if direct_label == "A" else trained_text
            output_b = trained_text if trained_label == "B" else direct_text
            judge_call = call_or_load(
                client,
                repetition_dir / "judge.json",
                messages=judge_messages(scenario, output_a, output_b),
                temperature=0,
                max_tokens=2200,
                json_output=True,
            )
            judge_value = parse_json_content(judge_call["content"])
            validate_judge(judge_value)
            label_to_condition = {direct_label: "direct", trained_label: "trained"}
            judge_winner = (
                "tie"
                if judge_value["winner"] == "tie"
                else label_to_condition[judge_value["winner"]]
            )
            sources = scenario["training_sources"] + [scenario["style_holdout"]]
            scores = {
                label_to_condition[label]: judge_value["scores"][label]
                for label in ("A", "B")
            }
            outputs = {"direct": direct_text, "trained": trained_text}
            overlaps = {
                condition: longest_source_match(text, sources)
                for condition, text in outputs.items()
            }
            length_range = scenario["length_range"]
            constraint_checks: dict[str, Any] = {}
            automatic_failures: dict[str, list[str]] = {}
            for label in ("A", "B"):
                condition = label_to_condition[label]
                character_count = visible_character_count(outputs[condition])
                length_passed = length_range["min"] <= character_count <= length_range["max"]
                failures = list(judge_value.get("automatic_failures", {}).get(label, []))
                if not length_passed:
                    failures.append(
                        f"长度硬约束失败：{character_count} 字，不在 "
                        f"{length_range['min']}—{length_range['max']} 字范围内"
                    )
                if overlaps[condition]["flagged"]:
                    failures.append(
                        f"连续文本重合风险：与 {overlaps[condition]['source']} "
                        f"重合 {overlaps[condition]['characters']} 字"
                    )
                automatic_failures[condition] = failures
                constraint_checks[condition] = {
                    "visible_characters": character_count,
                    "required_range": length_range,
                    "length_passed": length_passed,
                    "overlap_passed": not overlaps[condition]["flagged"],
                    "eligible": not failures,
                }
            eligible = [
                condition
                for condition in ("direct", "trained")
                if constraint_checks[condition]["eligible"]
            ]
            if len(eligible) == 1:
                winner = eligible[0]
                winner_basis = "hard_constraint_override"
            elif not eligible:
                winner = "tie"
                winner_basis = "both_failed_hard_constraints"
            else:
                winner = judge_winner
                winner_basis = "blind_pairwise_judge"
            repetition_results.append(
                {
                    "repetition": repetition,
                    "generation_order": conditions,
                    "blind_mapping": {"A": label_to_condition["A"], "B": label_to_condition["B"]},
                    "judge_winner": judge_winner,
                    "winner": winner,
                    "winner_basis": winner_basis,
                    "confidence": judge_value.get("confidence"),
                    "scores": scores,
                    "judge_summary": judge_value.get("summary", ""),
                    "criterion_findings": judge_value.get("criterion_findings", []),
                    "automatic_failures": automatic_failures,
                    "constraint_checks": constraint_checks,
                    "outputs": outputs,
                    "overlap": overlaps,
                    "models": {
                        "direct": calls["direct"].get("actual_model"),
                        "trained": calls["trained"].get("actual_model"),
                        "judge": judge_call.get("actual_model"),
                    },
                }
            )

        benchmark_scenarios.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "category": scenario["category"],
                "target": scenario["target"],
                "source_attribution": [
                    {
                        key: source[key]
                        for key in ("title", "url", "license", "role", "sha256")
                    }
                    for source in scenario["training_sources"] + [scenario["style_holdout"]]
                ],
                "writing_prompt": scenario["writing_prompt"],
                "evaluation_criteria": scenario["evaluation_criteria"],
                "trained_skill": custom_skill,
                "trained_style_profile": style_profile,
                "training_report": {
                    key: training_value.get(key)
                    for key in (
                        "evidence_summary",
                        "provisional_rules",
                        "excluded_surface_features",
                        "deterministic_repairs",
                    )
                },
                "repetitions": repetition_results,
                "summary": scenario_summary(repetition_results),
            }
        )

    overall_wins = {"trained": 0, "direct": 0, "tie": 0}
    overall_blind_preference = {"trained": 0, "direct": 0, "tie": 0}
    overall_eligible_outputs = {"trained": 0, "direct": 0}
    for scenario in benchmark_scenarios:
        for condition, count in scenario["summary"]["qualified_pairwise_results"].items():
            overall_wins[condition] += count
        for condition, count in scenario["summary"]["blind_preference"].items():
            overall_blind_preference[condition] += count
        for condition, count in scenario["summary"]["eligible_outputs"].items():
            overall_eligible_outputs[condition] += count
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "completed_at": datetime.now(UTC).isoformat(),
        "generator": "DeepSeek API only for training, direct generation, trained generation, and judging",
        "requested_model": args.model,
        "trainer_skill_sha256": sha256_text(trainer_skill),
        "scenario_dataset_sha256": sha256_text(args.scenarios.read_text(encoding="utf-8")),
        "repetitions_per_scenario": args.repetitions,
        "fairness_controls": [
            "The direct and trained conditions use the same requested model, user prompt, temperature, and max_tokens.",
            "Call order alternates by repetition.",
            "A/B labels are randomized before judging.",
            "The style holdout is excluded from training and shown only to the blind judge.",
            "Every repetition is retained; the public representative is repetition 1, fixed before judging.",
            "Exact normalized source overlap of 30 or more characters is flagged.",
        ],
        "overall_qualified_pairwise_results": overall_wins,
        "overall_blind_preference": overall_blind_preference,
        "overall_eligible_outputs": overall_eligible_outputs,
        "scenarios": benchmark_scenarios,
    }
    write_json(run_dir / "benchmark.json", result)
    result["usage"] = collect_usage(run_dir)
    write_json(run_dir / "benchmark.json", result)
    print(json.dumps({"run_dir": str(run_dir), "wins": overall_wins, "usage": result["usage"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
