#!/usr/bin/env python3
"""Build the frozen, attributed source set for the Writing Skill Trainer showcase."""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "scenarios.json"
CACHE_DIR = ROOT / ".cache" / "mediawiki"
USER_AGENT = "seasonsolt-writing-skill-showcase/1.0 (reproducible marketing benchmark)"


class ParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_paragraph = False
        self.ignored_depth = 0
        self.buffer: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script"}:
            self.ignored_depth += 1
        elif tag == "p":
            self.in_paragraph = True
            self.buffer = []
        elif tag == "br" and self.in_paragraph and not self.ignored_depth:
            self.buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if tag != "p" or not self.in_paragraph:
            return
        text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.buffer))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if text:
            self.paragraphs.append(text)
        self.in_paragraph = False
        self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.in_paragraph and not self.ignored_depth:
            self.buffer.append(data)


def request_json(url: str, attempts: int = 6) -> dict:
    cache_path = CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.load(response)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except urllib.error.HTTPError as error:
            if attempt == attempts - 1 or error.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else min(5 * 2**attempt, 60)
            time.sleep(delay)
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(2 * 2**attempt, 30))
    raise RuntimeError("unreachable")


def api_url(host: str, params: dict[str, object]) -> str:
    return f"https://{host}/w/api.php?{urllib.parse.urlencode(params)}"


def fetch_extract(host: str, title: str) -> tuple[str, str]:
    data = request_json(
        api_url(
            host,
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "titles": title,
                "prop": "extracts|info",
                "explaintext": 1,
                "inprop": "url",
            },
        )
    )
    page = data["query"]["pages"][0]
    if page.get("missing"):
        raise RuntimeError(f"Missing MediaWiki page: {host}/{title}")
    text = page.get("extract", "").strip()
    if not text:
        raise RuntimeError(f"Empty MediaWiki extract: {host}/{title}")
    text = clean_text(text)
    if host == "zh.wikinews.org":
        paragraphs = text.split("\n\n")
        while len(paragraphs) > 1 and len(paragraphs[-1]) < 80 and not re.search(r"[。！？.!?』”]$", paragraphs[-1]):
            paragraphs.pop()
        text = "\n\n".join(paragraphs)
    return text, page["fullurl"]


def fetch_rendered_paragraphs(host: str, title: str) -> tuple[str, str]:
    data = request_json(
        api_url(
            host,
            {
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "text|properties",
                "disableeditsection": 1,
            },
        )
    )
    parser = ParagraphParser()
    parser.feed(data["parse"]["text"]["*"])
    paragraphs: list[str] = []
    for paragraph in parser.paragraphs:
        plain = html.unescape(paragraph).replace("\u200b", "").strip()
        if not plain:
            continue
        if plain.startswith(("Public domain", "本作品現時", "这部作品", "1996年1月1日")):
            break
        paragraphs.append(plain)
    if not paragraphs:
        raise RuntimeError(f"No article paragraphs found: {host}/{title}")
    url = f"https://{host}/wiki/{urllib.parse.quote(title.replace(' ', '_'), safe='/():：') }"
    return "\n\n".join(paragraphs), url


def clean_text(text: str) -> str:
    text = text.replace("\u200b", "")
    text = re.sub(r"^(上一回\s+)?回目录\s+(下一回\s+)?", "", text)
    text = re.split(r"\n\s*==[^=\n]+==", text, maxsplit=1)[0]
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clip_at_paragraph(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    boundary = max(clipped.rfind("\n\n"), clipped.rfind("。"), clipped.rfind("！"), clipped.rfind("？"))
    if boundary >= int(limit * 0.72):
        clipped = clipped[: boundary + (0 if clipped[boundary : boundary + 2] == "\n\n" else 1)]
    return clipped.strip()


def source_record(title: str, url: str, text: str, license_name: str, role: str) -> dict:
    return {
        "title": title,
        "url": url,
        "license": license_name,
        "role": role,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
    }


def build_scenario(
    *,
    scenario_id: str,
    name: str,
    category: str,
    target: str,
    train_specs: list[tuple[str, str, str]],
    holdout_spec: tuple[str, str, str],
    fetcher,
    license_name: str,
    sample_limit: int,
    writing_prompt: str,
    evaluation_criteria: list[str],
    min_chars: int,
    max_chars: int,
    temperature: float,
    max_tokens: int,
) -> dict:
    train_sources = []
    for host, title, label in train_specs:
        text, url = fetcher(host, title)
        text = clip_at_paragraph(text, sample_limit)
        train_sources.append(source_record(label, url, text, license_name, "training"))
        time.sleep(0.6)
    host, title, label = holdout_spec
    holdout_text, holdout_url = fetcher(host, title)
    holdout_text = clip_at_paragraph(holdout_text, sample_limit)
    holdout = source_record(label, holdout_url, holdout_text, license_name, "style_holdout")
    return {
        "id": scenario_id,
        "name": name,
        "category": category,
        "target": target,
        "training_sources": train_sources,
        "style_holdout": holdout,
        "writing_prompt": writing_prompt.strip(),
        "evaluation_criteria": evaluation_criteria,
        "length_range": {"min": min_chars, "max": max_chars},
        "generation": {"temperature": temperature, "max_tokens": max_tokens},
    }


def main() -> None:
    scenarios = [
        build_scenario(
            scenario_id="red-chamber",
            name="《红楼梦》章回体续写",
            category="公版文学",
            target="从多章样本学习文白相间的叙事、以行动和对话显露人物关系、含蓄推进情绪，而非堆砌古语。",
            train_specs=[
                ("zh.wikisource.org", "紅樓夢/第001回", "《红楼梦》第一回"),
                ("zh.wikisource.org", "紅樓夢/第003回", "《红楼梦》第三回"),
                ("zh.wikisource.org", "紅樓夢/第005回", "《红楼梦》第五回"),
            ],
            holdout_spec=("zh.wikisource.org", "紅樓夢/第007回", "《红楼梦》第七回（留出）"),
            fetcher=fetch_extract,
            license_name="Public Domain（公版）",
            sample_limit=4300,
            writing_prompt="""
请用《红楼梦》的笔调，根据以下虚构情节续写一段 900—1200 字的章回体小说片段。不要照搬原著句子。

情节事实：初冬午后，大观园忽降小雪。史湘云提议众人各寻一件旧物作雪景题目；探春取出一柄断骨旧扇，宝玉认出是去年黛玉遗落之物，却不敢明说。宝钗看出端倪，以添炭为由支开丫鬟。黛玉后来入内，只问一句“这扇子怎么还没丢”，便转身看雪。结尾须以一个细小动作收住宝玉未说出口的话。不得新增重大身世秘密，不得引用原著诗句。
""",
            evaluation_criteria=[
                "章回体叙事自然推进，而不是古语和套话堆砌",
                "动作、称谓与对话共同显露人物亲疏和性情",
                "宝玉、黛玉、宝钗、湘云、探春的反应彼此有区分",
                "情绪转折含蓄，结尾以具体小动作收束",
                "不复制样本中的连续表达，不新增重大设定",
            ],
            min_chars=900,
            max_chars=1200,
            temperature=0.8,
            max_tokens=1800,
        ),
        build_scenario(
            scenario_id="restrained-satire",
            name="冷峻讽刺小说",
            category="公版文学机制迁移",
            target="用鲁迅公版小说展示从具体生活细节、叙述距离和反差中学习讽刺机制，而不是点名复刻在世作者。",
            train_specs=[
                ("zh.wikisource.org", "孔乙己", "鲁迅《孔乙己》"),
                ("zh.wikisource.org", "一件小事", "鲁迅《一件小事》"),
                ("zh.wikisource.org", "故鄉", "鲁迅《故乡》"),
            ],
            holdout_spec=("zh.wikisource.org", "藥", "鲁迅《药》（留出）"),
            fetcher=fetch_rendered_paragraphs,
            license_name="Public Domain（公版）",
            sample_limit=4300,
            writing_prompt="""
请把以下虚构素材写成 800—1100 字、冷峻克制的现代社会讽刺短篇。不得照搬任何名作句子。

素材：县城政务大厅上线“静音意见箱”。群众扫码后只能从“非常满意、满意、已了解”三项中选择；若停留超过十秒，屏幕会播放“感谢您的宝贵意见”。临时工作人员周河每天负责统计，报表里连续三十天“零投诉”。一位修鞋老人不会扫码，拿来一封手写信。主任让周河“帮助老人完成数字化表达”。下班前，周河在系统里替老人选择了“已了解”，却把那封信夹进自己的考勤本。第二天，系统表扬大厅实现连续三十一天零投诉。
""",
            evaluation_criteria=[
                "讽刺来自制度语言与现实细节的反差，而非段子堆叠",
                "叙述者保持克制距离，人物不沦为观点喇叭",
                "修鞋老人、周河和主任通过动作或话语呈现层次",
                "结尾冷静有余味，不直接总结中心思想",
                "现代中文可读且不复制训练或留出文本",
            ],
            min_chars=800,
            max_chars=1100,
            temperature=0.8,
            max_tokens=1700,
        ),
        build_scenario(
            scenario_id="tech-news",
            name="中性科技新闻报道",
            category="栏目/品牌文风",
            target="从多篇开放许可报道训练出稳定的导语、归因、倒金字塔结构与中性语气，并严格受事实包约束。",
            train_specs=[
                ("zh.wikinews.org", "斯坦福AI研究所发布2023年AI指数 报告人工智能最新进展", "维基新闻：2023 AI 指数"),
                ("zh.wikinews.org", "中國科技部長：ChatGPT算法質量高 亦指推進6G研發", "维基新闻：ChatGPT 与 6G"),
                ("zh.wikinews.org", "Copilot：微軟將GPT-4 AI技術納入辦公軟件 一鍵生成內容", "维基新闻：Microsoft Copilot"),
            ],
            holdout_spec=("zh.wikinews.org", "Google揭AI超级电脑晶片TPU 称比英伟达A100更快更节能", "维基新闻：Google TPU（留出）"),
            fetcher=fetch_extract,
            license_name="CC BY 2.5；来源：中文维基新闻",
            sample_limit=2600,
            writing_prompt="""
根据下列虚构事实包写一篇 450—650 字的中文科技新闻。不得补造引语、背景数字或评价，正文末尾不要附字数说明。

事实包：
- 2026 年 4 月 18 日，虚构城市“澄江市”的公共数据局发布“桥灯”城市数据开放平台测试版。
- 首批开放 42 个数据集，涉及公交到站、公共停车位、空气质量和图书馆座位；更新频率从 5 分钟到 24 小时不等。
- 数据局称，平台采用统一接口，测试期为三个月；个人身份信息不在开放范围内。
- 三所本地高校和 12 家小微企业参与首轮测试。
- 参与测试的“青禾科技”产品负责人林岚仅表示，统一字段减少了前期清洗工作；未提供效率提升数字。
- 市民可查看数据目录，但调用接口须实名注册。平台尚未公布测试期后的收费政策和故障响应标准。
- 一名未具名的数据治理研究者提醒，开放频率、历史数据完整性和接口稳定性仍需在测试中观察。
- 发布会上没有公布总建设成本。
""",
            evaluation_criteria=[
                "导语迅速交代主体、事件、时间和最重要结果",
                "采用倒金字塔组织，关键信息先于次要背景",
                "明确归因，事实、机构说法和外部提醒不混淆",
                "严格使用事实包，不补造引语、数字或结论",
                "语言中性、紧凑，避免宣传腔和主观形容",
            ],
            min_chars=450,
            max_chars=650,
            temperature=0.45,
            max_tokens=1300,
        ),
    ]
    payload = {
        "schema_version": 1,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "methodology": {
            "training_sources_per_scenario": 3,
            "style_holdouts_per_scenario": 1,
            "note": "Style holdouts are never included in the training prompt; they are shown only to the blind judge.",
        },
        "scenarios": scenarios,
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {DATA_PATH} ({DATA_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
