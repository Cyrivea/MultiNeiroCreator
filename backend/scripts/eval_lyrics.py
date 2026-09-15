"""歌词生成评测脚本：baseline vs tuned。

- baseline：只给主题，不带 style/mood 参数；
- tuned：带 style/mood；
- 每个主题各生成一次，共 40 次生成 + 20 次评委评分（串行，带进度打印）；
- 机判（规则化最低合格标准）+ LLM-as-judge（双盲 A/B）并存，结果写入
  ``eval_result.json``，顶层键：meta / mechanical / judge。

运行（backend/ 下）：``uv run python scripts/eval_lyrics.py``
"""

import json
import os
import random
import sys

# 评测需要直连智谱：清掉环境里可能存在的 HTTP(S) 代理（本机 Clash WSL 转发会挂起请求）。
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_k, None)

from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from schemas.capability import LyricsGenerateInput
from services.capabilities.zhipu_text import generate_lyrics_text, load_lyrics_model

THEMES = [
    "毕业", "失恋", "暗恋", "重逢", "告别",
    "夏夜", "雨后的城市", "凌晨四点", "末班地铁", "海边公路",
    "国风", "赛博朋克", "废墟之城", "深海", "祭典",
    "时间", "孤独", "故乡", "光", "梦",
]

MIN_LINES = 8
REFUSAL_HINTS = ["我无法", "对不起", "作为AI"]
JUDGE_DIMENSIONS = ["切题度", "意象与修辞", "情感递进", "韵脚节奏"]
# 使用固定随机种子，保证同一环境多次跑的 A/B 分配一致，结果可复现
AB_SEED = 20_260_914


def judge(text: str) -> dict:
    """机判的结构化结果：每条 check 单独标出，失败样本才知道挂在哪条规则。"""
    stripped = [line for line in text.strip().splitlines() if line.strip()]
    checks = {
        "structure": any(k in text for k in ("主歌", "副歌", "桥段")),
        "not_empty": bool(stripped) and not any(h in text for h in REFUSAL_HINTS),
        "enough_lines": len(stripped) >= MIN_LINES,
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "line_count": len(stripped),
    }


def build_inputs(theme: str, with_params: bool) -> LyricsGenerateInput:
    """对照的唯一变量：是否给风格引导。"""
    if with_params:
        return LyricsGenerateInput(theme=theme, style="流行抒情", mood="温柔、克制")
    return LyricsGenerateInput(theme=theme)


def evaluate_mechanical(theme: str, group: str, output: str) -> tuple[dict, float]:
    """单个主题的机判结果条目。返回 (group 清单条目, rate 占位由聚合完成)。"""
    result = judge(output)
    item = {
        "theme": theme,
        "passed": result["pass"],
        "failed_checks": [name for name, ok in result["checks"].items() if not ok],
        "line_count": result["line_count"],
    }
    if not result["pass"]:
        item["output"] = output[:200]
    return item, 1.0 if result["pass"] else 0.0


def main() -> None:
    # ---------- 1. 生成：每组各主题只跑一遍，结果保存下来供评委复用 ----------
    outputs: dict[str, dict[str, str]] = {"baseline": {}, "tuned": {}}
    mechanical_raw = {"baseline": [], "tuned": []}
    mechanical = {}
    for group in ("baseline", "tuned"):
        with_params = group == "tuned"
        pass_count = 0
        for index, theme in enumerate(THEMES, start=1):
            print(f"[{group}][{index}/{len(THEMES)}] {theme} 生成中…", flush=True)
            try:
                text = generate_lyrics_text(build_inputs(theme, with_params))
            except Exception as exc:  # 单次生成失败也入账，不中断评测
                outputs[group][theme] = ""
                mechanical_raw[group].append(
                    {
                        "theme": theme,
                        "passed": False,
                        "failed_checks": ["generation_error"],
                        "line_count": 0,
                        "output": type(exc).__name__,
                    }
                )
                continue
            outputs[group][theme] = text
            item, passed = evaluate_mechanical(theme, group, text)
            mechanical_raw[group].append(item)
            pass_count += passed
        mechanical[group] = {
            "passed": int(pass_count),
            "total": len(THEMES),
            "rate": pass_count / len(THEMES) if THEMES else 0,
            "items": mechanical_raw[group],
            "failures": [item for item in mechanical_raw[group] if not item["passed"]],
        }

    # ---------- 2. 评委：双盲 A/B，同一主题两份输出 ----------
    rng = random.Random(AB_SEED)
    per_theme: list[dict] = []
    for index, theme in enumerate(THEMES, start=1):
        mapping = {"A": "baseline", "B": "tuned"} if rng.random() < 0.5 else {"A": "tuned", "B": "baseline"}
        a_text = outputs[mapping["A"]][theme]
        b_text = outputs[mapping["B"]][theme]
        print(f"[judge][{index}/{len(THEMES)}] {theme} 评分中…", flush=True)
        scores = judge_theme_with_llm(theme, a_text, b_text)
        record: dict = {"theme": theme, "ab_mapping": mapping}
        if "eval_error" in scores:
            record["eval_error"] = scores["eval_error"]
        else:
            record.update({"A": scores.get("A", {}), "B": scores.get("B", {}), "总体偏好": scores.get("总体偏好", "平")})
        per_theme.append(record)

    summary = summarize_judge(per_theme)
    result = {
        "meta": {
            "themes_count": len(THEMES),
            "model": config.LYRICS_MODEL,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        "mechanical": mechanical,
        "judge": {"per_theme": per_theme, "summary": summary},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    with open("eval_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n已写入 eval_result.json")


JUDGE_PROMPT = """你是一名中立的歌词评审。请比较 A 和 B 两个歌词版本。
硬性要求：
- 不知道哪一版来自哪组实验参数，你只评价文本本身。
- 按四个维度分别打 1~10 分：切题度、意象与修辞、情感递进、韵脚节奏。
- 最后给出总体偏好：A / B / 平。
- 只输出 JSON，不要输出任何解释、Markdown 或代码块。

输出格式（严格遵守）：
{"A": {"切题度": 1, "意象与修辞": 1, "情感递进": 1, "韵脚节奏": 1},
 "B": {"切题度": 1, "意象与修辞": 1, "情感递进": 1, "韵脚节奏": 1},
 "总体偏好": "A"}

主题：{theme}

---
A 版：
{a_text}

---
B 版：
{b_text}
"""


def judge_theme_with_llm(theme: str, a_text: str, b_text: str) -> dict:
    """单次评委调用；失败也要返回结构化 error 字段，不中断整场评测。"""
    model = load_lyrics_model()
    if model is None:
        return {"eval_error": "评审模型未配置"}
    try:
        response = model.chat.completions.create(
            model=config.LYRICS_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是中立的歌词评审，只按要求输出 JSON 评分，不得解释。",
                },
                {"role": "user", "content": JUDGE_PROMPT.format(theme=theme, a_text=a_text, b_text=b_text)},
            ],
            temperature=0.1,
            stream=False,
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            return {"eval_error": "评审模型返回空内容"}
        return json.loads(content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    except Exception as exc:  # 评审失败记为 eval_error，不中断整场评测
        return {"eval_error": f"{type(exc).__name__}: {exc}"}


def summarize_judge(per_theme: list[dict]) -> dict:
    """按 A/B 揭盲映射回 baseline/tuned，汇总各维度均分和胜负平。"""
    dimension_sums = {"baseline": {d: 0.0 for d in JUDGE_DIMENSIONS}, "tuned": {d: 0.0 for d in JUDGE_DIMENSIONS}}
    preference = {"baseline_wins": 0, "tuned_wins": 0, "ties": 0}
    scored_count = 0
    for item in per_theme:
        if "eval_error" in item:
            continue
        mapping = item["ab_mapping"]
        scores_a = item.get("A", {})
        scores_b = item.get("B", {})
        if not scores_a or not scores_b:
            continue
        scored_count += 1
        baseline_scores = scores_a if mapping["A"] == "baseline" else scores_b
        tuned_scores = scores_b if mapping["B"] == "tuned" else scores_a
        for dim in JUDGE_DIMENSIONS:
            dimension_sums["baseline"][dim] += float(baseline_scores.get(dim, 0))
            dimension_sums["tuned"][dim] += float(tuned_scores.get(dim, 0))
        pref = item.get("总体偏好")
        if pref == "A":
            preference["baseline_wins" if mapping["A"] == "baseline" else "tuned_wins"] += 1
        elif pref == "B":
            preference["tuned_wins" if mapping["B"] == "tuned" else "baseline_wins"] += 1
        else:
            preference["ties"] += 1
    per_dimension = {
        group: {dim: (dimension_sums[group][dim] / scored_count if scored_count else 0) for dim in JUDGE_DIMENSIONS}
        for group in ("baseline", "tuned")
    }
    return {"per_dimension_means": per_dimension, "preference": preference, "scored_themes": scored_count}


if __name__ == "__main__":
    main()
