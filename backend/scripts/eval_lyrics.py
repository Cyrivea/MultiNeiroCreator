"""歌词生成评测脚本：baseline vs tuned。

- baseline：只给主题，不带 style/mood 参数；
- tuned：带 style/mood；
- 每个主题各生成一次，共 40 次生成 + 每主题两轮评委评分（串行，带进度打印）；
- 机判（规则化最低合格标准）+ LLM-as-judge（双盲 A/B，位置交换复评）并存；
- 结果写入 ``eval_result.json``，顶层键：meta / mechanical / judge。

运行（backend/ 下）：

    uv run python scripts/eval_lyrics.py              # 真实跑模型
    uv run python scripts/eval_lyrics.py --dry-run    # mock 生成+评委，验证流程
"""

import argparse
import json
import os
import random
import sys

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

AB_SEED = 20_260_914
DRY_RUN_OUTPUT = "eval_result.dryrun.json"


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


def evaluate_mechanical(output: str) -> tuple[dict, float]:
    """单个主题的机判结果条目。返回 (条目, 是否通过的 0/1)。"""
    result = judge(output)
    item = {
        "passed": result["pass"],
        "failed_checks": [name for name, ok in result["checks"].items() if not ok],
        "line_count": result["line_count"],
    }
    if not result["pass"]:
        item["output"] = output[:200]
    return item, 1.0 if result["pass"] else 0.0


def generate_outputs(theme: str, with_params: bool) -> str:
    """真实模式走 Provider；dry-run 返回带 group 记号的假文本。

    2026-09-24 适配：generate_lyrics_text 自 usage_events 账本改造（d76b53b）后
    返回 {content, usage}，评测只取正文。
    """
    return generate_lyrics_text(build_inputs(theme, with_params))["content"]


def generate_outputs_fake(theme: str, with_params: bool) -> str:
    """dry-run 用：tuned 永远比 baseline 长，方便验证 A/B 交换逻辑的确定性。"""
    body = f"{theme} · " + ("主歌 副歌 桥段 " * 4)
    return body if not with_params else body + "（强化意象版）"


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


def _scores(prefer: str) -> dict:
    """按偏好位置构造一份评委输出。「平」时当场相同分数。"""
    base_a = 7 if prefer == "A" else 6
    base_b = 7 if prefer == "B" else 6
    a_scores = {dim: base_a for dim in JUDGE_DIMENSIONS}
    b_scores = {dim: base_b for dim in JUDGE_DIMENSIONS}
    return {"A": a_scores, "B": b_scores, "总体偏好": prefer}


def judge_theme_with_llm_once(theme: str, a_text: str, b_text: str) -> dict:
    """单次评委调用。"""
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
                {
                    "role": "user",
                    "content": JUDGE_PROMPT.format(theme=theme, a_text=a_text, b_text=b_text),
                },
            ],
            temperature=0.1,
            stream=False,
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            return {"eval_error": "评审模型返回空内容"}
        return json.loads(
            content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
    except Exception as exc:
        return {"eval_error": f"{type(exc).__name__}: {exc}"}


def judge_theme_with_llm(theme: str, a_text: str, b_text: str) -> dict:
    """带一次重试的评委调用；两次都失败才记为 eval_error，评测不中断。"""
    for attempt in (1, 2):
        result = judge_theme_with_llm_once(theme, a_text, b_text)
        if "eval_error" not in result or attempt == 2:
            return result
    return result


def judge_theme_dry_run(theme: str, a_text: str, b_text: str, preferred: str | None) -> dict:
    """dry-run 用：按 preferred 提示判赢；preferred=None 时判平分。"""
    return _scores(preferred or "平")


def _judge_round(theme: str, a_text: str, b_text: str, dry_run: bool, dry_prefer: str | None) -> dict:
    if dry_run:
        return judge_theme_dry_run(theme, a_text, b_text, dry_prefer)
    return judge_theme_with_llm(theme, a_text, b_text)


def _content_of(mapping: dict[str, str], position_verdict: str) -> str:
    """把「A/B/平」的位置偏好翻译成 baseline/tuned/tie。"""
    if position_verdict == "平":
        return "tie"
    return mapping.get(position_verdict, "tie")


def evaluate_theme(
    theme: str,
    outputs: dict[str, dict[str, str]],
    rng: random.Random,
    *,
    dry_run: bool,
    dry_bias_theme: str | None = None,
) -> dict:
    """一个主题两轮评委：第一轮随机 A/B，第二轮强制交换；汇总偏倚与最终结论。"""
    # 第 1 轮：随机决定谁是 A、谁是 B。
    mapping1 = {"A": "baseline", "B": "tuned"} if rng.random() < 0.5 else {"A": "tuned", "B": "baseline"}
    a_text = outputs[mapping1["A"]][theme]
    b_text = outputs[mapping1["B"]][theme]
    # dry-run 下：bias 主题总是给 A 位赢，用来验证位置偏倚检出；其他主题按文本长短判 tuned 赢。
    dry_prefer = "A" if dry_bias_theme == theme else ("B" if len(b_text) > len(a_text) else "平")
    round1 = _judge_round(theme, a_text, b_text, dry_run, dry_prefer)

    # 第 2 轮：强制交换位置。
    mapping2 = {"A": mapping1["B"], "B": mapping1["A"]}
    a2_text = outputs[mapping2["A"]][theme]
    b2_text = outputs[mapping2["B"]][theme]
    dry_prefer2 = "A" if dry_bias_theme == theme else ("B" if len(b2_text) > len(a2_text) else "平")
    round2 = _judge_round(theme, a2_text, b2_text, dry_run, dry_prefer2)

    # ---------- 取两轮交集，得出最终结论 ----------
    record: dict = {
        "theme": theme,
        "rounds": [
            {"position_mapping": mapping1, "result": round1},
            {"position_mapping": mapping2, "result": round2},
        ],
        "position_bias": False,
        "final_verdict": "unknown",
    }
    for round_result in (round1, round2):
        if "eval_error" in round_result:
            record["final_verdict"] = "unknown"
            record["eval_errors"] = [
                r["eval_error"] for r in (round1, round2) if "eval_error" in r
            ]
            return record

    pos1 = round1.get("总体偏好", "平")
    pos2 = round2.get("总体偏好", "平")
    c1 = _content_of(mapping1, pos1)
    c2 = _content_of(mapping2, pos2)

    if pos1 == pos2 and pos1 != "平":
        # 两轮都把票投给同一个位置：内容随位置翻转，是真正的位置偏倚。
        record["position_bias"] = True
        record["final_verdict"] = "biased"
    elif c1 == c2:
        # 两轮票投给同一内容：有效胜负或有效平局。
        record["final_verdict"] = c1
    elif "tie" in (c1, c2):
        # 一次胜一次平 → 弱胜负
        record["final_verdict"] = f"weak_{c1 if c2 == 'tie' else c2}"
    else:
        # 两轮指向相反内容且位置也换了：结论不稳定，一锅端
        record["final_verdict"] = "inconclusive"
    return record


def summarize_judge(per_theme: list[dict]) -> dict:
    """按最终结论汇总；偏倚样本不参与胜负统计，单独列出。"""
    dimension_sums = {
        "baseline": {dim: 0.0 for dim in JUDGE_DIMENSIONS},
        "tuned": {dim: 0.0 for dim in JUDGE_DIMENSIONS},
    }
    preference = {
        "baseline_wins": 0,
        "tuned_wins": 0,
        "ties": 0,
        "weak_baseline": 0,
        "weak_tuned": 0,
        "biased": 0,
        "inconclusive": 0,
        "unknown": 0,
    }
    scored_rounds = 0
    for item in per_theme:
        pref = item.get("final_verdict", "unknown")
        if pref == "baseline":
            preference["baseline_wins"] += 1
        elif pref == "tuned":
            preference["tuned_wins"] += 1
        elif pref == "tie":
            preference["ties"] += 1
        elif pref == "weak_baseline":
            preference["weak_baseline"] += 1
        elif pref == "weak_tuned":
            preference["weak_tuned"] += 1
        elif pref == "biased":
            preference["biased"] += 1
        elif pref == "inconclusive":
            preference["inconclusive"] += 1
        else:
            preference["unknown"] += 1

        if pref in {"biased", "unknown"}:
            continue
        for round_entry in item.get("rounds", []):
            result = round_entry.get("result", {})
            mapping = round_entry.get("position_mapping", {})
            scores_a = result.get("A")
            scores_b = result.get("B")
            if not scores_a or not scores_b:
                continue
            scored_rounds += 1
            for dim in JUDGE_DIMENSIONS:
                # 位置 A/B 的分数先揭盲映射回 baseline/tuned 再累计
                dimension_sums["baseline"][dim] += float(
                    (scores_a if mapping.get("A") == "baseline" else scores_b).get(dim, 0)
                )
                dimension_sums["tuned"][dim] += float(
                    (scores_a if mapping.get("A") == "tuned" else scores_b).get(dim, 0)
                )

    per_dimension = {
        group: {
            dim: (dimension_sums[group][dim] / scored_rounds if scored_rounds else 0.0)
            for dim in JUDGE_DIMENSIONS
        }
        for group in ("baseline", "tuned")
    }
    return {
        "total_themes": len(per_theme),
        "position_bias_count": preference["biased"],
        "position_bias_ratio": (preference["biased"] / len(per_theme)) if per_theme else 0,
        "preference": preference,
        "per_dimension_means": per_dimension,
        "scored_rounds": scored_rounds,
    }


def run_group(group: str, outputs: dict[str, str], *, dry_run: bool) -> dict:
    passed = 0
    failures: list[dict] = []
    for index, theme in enumerate(THEMES, start=1):
        print(f"[{group}][{index}/{len(THEMES)}] {theme} 生成中…", flush=True)
        if dry_run:
            text = generate_outputs_fake(theme, group == "tuned")
        else:
            try:
                text = generate_outputs(theme, group == "tuned")
            except Exception as exc:
                outputs[theme] = ""
                failures.append(
                    {
                        "theme": theme,
                        "passed": False,
                        "failed_checks": ["generation_error"],
                        "line_count": 0,
                        "output": type(exc).__name__,
                    }
                )
                continue
        outputs[theme] = text
        item, passed_flag = evaluate_mechanical(text)
        item["theme"] = theme
        passed += passed_flag
        if not passed_flag:
            failures.append(item)
    return {
        "passed": int(passed),
        "total": len(THEMES),
        "rate": passed / len(THEMES) if THEMES else 0,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="歌词生成评测：baseline vs tuned")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不调用真实模型；mock 生成与评委（验证 A/B 交换、偏倚和汇总逻辑），输出 eval_result.dryrun.json",
    )
    args = parser.parse_args()

    outputs: dict[str, dict[str, str]] = {"baseline": {}, "tuned": {}}
    mechanical = {}
    for group in ("baseline", "tuned"):
        mechanical[group] = run_group(group, outputs[group], dry_run=args.dry_run)

    rng = random.Random(AB_SEED)
    per_theme: list[dict] = []
    bias_probe_theme = THEMES[13] if args.dry_run else None  # dry-run 时由“深海”验证偏倚检出
    for theme in THEMES:
        print(f"[judge] {theme} 评分中…", flush=True)
        per_theme.append(
            evaluate_theme(
                theme,
                outputs,
                rng,
                dry_run=args.dry_run,
                dry_bias_theme=bias_probe_theme,
            )
        )

    summary = summarize_judge(per_theme)
    result = {
        "meta": {
            "themes_count": len(THEMES),
            "model": config.LYRICS_MODEL,
            "timestamp": datetime.now(UTC).isoformat(),
            "dry_run": args.dry_run,
        },
        "mechanical": mechanical,
        "judge": {"per_theme": per_theme, "summary": summary},
    }
    output_file = DRY_RUN_OUTPUT if args.dry_run else "eval_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n已写入 {output_file}")


if __name__ == "__main__":
    main()
