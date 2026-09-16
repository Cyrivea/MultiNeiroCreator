"""意图→动作评测（B20 / W2）。

判的不是歌词好不好听，是“模型在真实口吻下选择哪个工具、按什么顺序调”。
与生产的唯一连接:

- system prompt = `agents.neyria.build_system_prompt`（真身，不是抄一遍）；
- tools schema = `_tools_for_context(False)`（和生产无知识库分支一致）；
- 执行器改成 in-memory 桩（模拟 configure/run/status 的真实返回形状与拒绝规则），
  模型看到的工具反馈和生产同构，但不会动真数据库。

每条用例给一个场景（画布状态）+ 用户真实口吻的一句话 + 断言（必须按序调哪些、禁调哪些、
是否应该“澄清而不是硬跑”）。

运行（backend/ 下）：
    uv run python scripts/eval_intent.py            # 真实模型跑全量
    uv run python scripts/eval_intent.py --dry-run  # mock 模型，验证评测器自身
    uv run python scripts/eval_intent.py --only 串联

结果写 eval_intent_result.json。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# 评测直连模型：清掉代理避免本地工具转发挂起
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_k, None)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.neyria import build_system_prompt, client
from services.chat.chat_orchestrator import _tools_for_context

RESULT_FILE = Path(__file__).resolve().parents[1] / "eval_intent_result.json"
DRY_RESULT_FILE = Path(__file__).resolve().parents[1] / "eval_intent_result.dryrun.json"

LATEST_MODEL = None  # 会读 config.CHAT_MODEL
MAX_ROUNDS = 6

# ---------------------------------------------------------------------------
# 假画布：模拟服务端的状态与拒绝规则（不碰真库）
# ---------------------------------------------------------------------------


class FakeCanvas:
    """一个非常朴素的 in-memory Draft + run 状态机，行为语义对齐生产。"""

    def __init__(self, nodes: list[dict] | None = None, active_run: bool = False):
        self.nodes: list[dict[str, Any]] = list(nodes or [])
        self.active_run = active_run
        self.edges: list[dict[str, str]] = []
        self._next_id = 0

    def has_capability(self, cap: str) -> bool:
        return any(n.get("capability_id") == cap for n in self.nodes)

    def latest_capability_id(self, cap: str) -> str | None:
        for n in reversed(self.nodes):
            if n.get("capability_id") == cap:
                return n["id"]
        return None

    def to_summary(self) -> dict:
        return {
            "status": "ok",
            "revision": len(self.nodes) + 1,
            "workflow_id": 1,
            "nodes": [
                {
                    "id": n["id"],
                    "name": n["name"],
                    "capability_id": n.get("capability_id"),
                    "params": n.get("params") or {},
                    "run_status": n.get("runStatus"),
                }
                for n in self.nodes
            ],
            "edges": self.edges,
        }

    def configure(self, capability_id: str, tool_type: str, params: dict, upstream: str | None) -> dict:
        # 生产的硬护栏：引用上游但没连线 -> 拒绝（模型必须看到这条）
        referenced = any(isinstance(v, str) and ".result.content}" in v for v in params.values())
        if referenced and upstream is None and not self._has_inbound_from(capability_id):
            return {
                "status": "rejected",
                "error": "检测到参数引用了上游结果，但该节点没有任何上游连线，运行时无法取到上游内容。",
                "message": "请先调用 read_workflow_state，并用 upstream_node_id 串联后重试。",
            }
        node_id = self.latest_capability_id(capability_id)
        if node_id is None:
            self._next_id += 1
            node_id = f"workflow-node-{tool_type}-{self._next_id:04d}"
            self.nodes.append(
                {
                    "id": node_id,
                    "name": f"{tool_type}生成",
                    "capability_id": capability_id,
                    "params": params,
                    "runStatus": "idle",
                }
            )
        else:
            for n in self.nodes:
                if n["id"] == node_id:
                    n["params"] = params
                    n["runStatus"] = "idle"
        if upstream:
            self.edges.append({"source": upstream, "target": node_id})
        elif not any(e["target"] == node_id for e in self.edges):
            self.edges.append({"source": "workflow-input", "target": node_id})
        self.edges.append({"source": node_id, "target": "workflow-output"})
        _dedup = []
        seen = set()
        for e in self.edges:
            k = (e["source"], e["target"])
            if k not in seen:
                seen.add(k)
                _dedup.append(e)
        self.edges = _dedup
        return {
            "status": "configured",
            "node_id": node_id,
            "message": "已在工作区创建/配置节点。",
        }

    def _has_inbound_from(self, capability_id: str) -> bool:
        node_id = self.latest_capability_id(capability_id)
        if node_id is None:
            return False
        return any(
            e["target"] == node_id and e["source"] != "workflow-input" for e in self.edges
        )

    def run(self) -> dict:
        if self.active_run:
            return {
                "status": "rejected",
                "error": "WORKFLOW_BUSY：已有 Workflow 正在运行",
                "message": "请先查询进度或等待其结束。",
            }
        caps = [n for n in self.nodes if n.get("capability_id")]
        if not caps:
            return {"status": "rejected", "error": "Workflow 里还没有可执行的生产工具节点"}
        for n in caps:
            n["runStatus"] = "running"
        self.active_run = True
        return {
            "status": "queued",
            "run_id": "run-eval-1",
            "message": "Workflow 已排队执行，可追问进度。",
        }

    def finish_run(self) -> None:
        for n in self.nodes:
            if n.get("capability_id") and n.get("runStatus") == "running":
                n["runStatus"] = "succeeded"
                n["result"] = {"content": "[fake-content]"}
        self.active_run = False


# ---------------------------------------------------------------------------
# 用例集：真实口吻 + 场景 + 断言
# ---------------------------------------------------------------------------


def _base_draft() -> list[dict]:
    return [
        {"id": "workflow-input", "name": "输入", "kind": "endpoint"},
        {"id": "workflow-output", "name": "输出", "kind": "endpoint"},
    ]


CASES: list[dict[str, Any]] = [
    # ---- 单纯歌词 ----
    {
        "name": "单独写歌词",
        "user": "帮我写一首关于夏天海边的歌",
        "setup": "empty",
        "must_in_order": ["configure_lyrics_workflow", "run_current_workflow"],
        "must_not": ["clear_workflow_draft", "search_web"],
    },
    {
        "name": "换风格重跑歌词（已有歌词节点）",
        "user": "把刚才那首换成摇滚风格再生成一次",
        "setup": "lyrics_done",
        "must_in_order": ["configure_lyrics_workflow", "run_current_workflow"],
        "must_not": ["clear_workflow_draft"],
    },
    # ---- 串联 ----
    {
        "name": "串联：歌词→曲绘",
        "user": "写个失恋主题的歌词，再根据歌词内容串联生成一张曲绘",
        "setup": "empty",
        "must_in_order": [
            "configure_lyrics_workflow",
            "configure_image_workflow",
            "run_current_workflow",
        ],
        "must_not": ["clear_workflow_draft", "search_web"],
        "extra_assert": "image_has_upstream",
    },
    {
        "name": "串联（先 A 后 B 口吻）",
        "user": "先帮我写段副歌歌词，写完直接拿去做封面图",
        "setup": "empty",
        "must_in_order": [
            "configure_lyrics_workflow",
            "configure_image_workflow",
            "run_current_workflow",
        ],
        "must_not": ["clear_workflow_draft"],
        "extra_assert": "image_has_upstream",
    },
    # ---- 进度追问（画布在跑） ----
    {
        "name": "追问进度（画布在跑）",
        "user": "跑得怎么样了？",
        "setup": "active_run",
        "must_call_any_of": ["get_workflow_run_status", "wait_for_workflow_completion"],
        "must_not": ["run_current_workflow", "configure_lyrics_workflow", "clear_workflow_draft"],
    },
    {
        "name": "用户说继续但还在跑（不许重复提交）",
        "user": "继续",
        "setup": "active_run",
        "must_call_any_of": ["get_workflow_run_status", "wait_for_workflow_completion"],
        "must_not": ["run_current_workflow", "clear_workflow_draft"],
    },
    # ---- 查看画布 ----
    {
        "name": "问画布状态",
        "user": "画布上现在有哪些节点？",
        "setup": "lyrics_done",
        "must_in_order": ["read_workflow_state"],
        "must_not": ["configure_lyrics_workflow", "run_current_workflow"],
    },
    # ---- 清空重建（唯一允许 clear 的口吻） ----
    {
        "name": "明确清空重建",
        "user": "全都不要了，清空画布，我要重新搭",
        "setup": "lyrics_done",
        "must_in_order": ["clear_workflow_draft"],
        "must_not": [],
    },
    # ---- 歧义场景：该追问而不是硬跑 ----
    {
        "name": "含糊“再来一版”（无任何上下文）",
        "user": "再来一版",
        "setup": "empty",
        "expect_no_side_effect": True,
    },
    {
        "name": "含糊“把它改得更好听点”（无可指代对象）",
        "user": "把它改得更好听一点",
        "setup": "empty",
        "expect_no_side_effect": True,
    },
    # ---- 普通知识问答不应碰工作流 ----
    {
        "name": "纯聊天不碰工作流",
        "user": "副歌和主歌在结构上一般怎么区分？",
        "setup": "empty",
        "must_not": [
            "configure_lyrics_workflow",
            "configure_image_workflow",
            "run_current_workflow",
            "clear_workflow_draft",
        ],
        "expect_no_side_effect": True,
    },
    # ---- 追问歌词修改 ----
    {
        "name": "改歌词主题重跑",
        "user": "把主题改成告别再生成一版",
        "setup": "lyrics_done",
        "must_in_order": ["configure_lyrics_workflow", "run_current_workflow"],
        "must_not": ["clear_workflow_draft"],
    },
    # ---- 并联口吻 ----
    {
        "name": "并联口吻（同时做歌词和海报）",
        "user": "歌词和海报同时帮我做一下",
        "setup": "empty",
        "must_in_order": [
            "configure_lyrics_workflow",
            "configure_image_workflow",
            "run_current_workflow",
        ],
        "must_not": ["clear_workflow_draft"],
        # 并联是允许的：至少不要错把“并联”做成“串联引用上游”
        "extra_assert": "image_no_upstream_ref",
    },
    # ---- 历史污染场景（生产真实踩过的坑） ----
    {
        "name": "历史失败不冻结：上次曲绘没模型，这次重试歌词要能跑",
        "user": "歌词再给我出一版，主题换成海边",
        "setup": "chained_done",
        "history": [
            {"role": "user", "content": "写个失恋主题的歌词并串联出曲绘"},
            {"role": "assistant", "content": "歌词已生成；曲绘因图像模型尚未配置暂未产出，留节点待以后重跑。"},
        ],
        "must_in_order": ["configure_lyrics_workflow", "run_current_workflow"],
        "must_not": ["clear_workflow_draft"],
    },
    {
        "name": "历史空谈后追问：必须查状态而不是顺香葱谎",
        "user": "现在跑得怎么样了？",
        "setup": "active_run",
        "history": [
            {"role": "user", "content": "写歌词串联出曲绘"},
            {"role": "assistant", "content": "Workflow 已排队执行，画布节点会实时显示运行状态。"},
        ],
        "must_call_any_of": ["get_workflow_run_status", "wait_for_workflow_completion"],
        "must_not": ["run_current_workflow", "configure_image_workflow"],
    },
    # ---- 画布上已有_FULL链路时，用户追加小改 ----
    {
        "name": "已有完整链路，追加微调",
        "user": "歌词情绪改成更忧郁一点重新跑",
        "setup": "chained_done",
        "must_in_order": ["configure_lyrics_workflow", "run_current_workflow"],
        "must_not": ["clear_workflow_draft", "configure_image_workflow"],
    },
]


def setup_canvas(kind: str) -> FakeCanvas:
    c = FakeCanvas(_base_draft())
    if kind == "empty":
        return c
    if kind == "lyrics_done":
        c.configure("lyrics.generate", "lyrics", {"theme": "夏夜"}, None)
        c.run()
        c.finish_run()
        return c
    if kind == "active_run":
        c.configure("lyrics.generate", "lyrics", {"theme": "夏夜"}, None)
        c.run()  # runStatus=running, active_run=True
        return c
    if kind == "chained_done":
        c.configure("lyrics.generate", "lyrics", {"theme": "夏夜"}, None)
        lyr = c.latest_capability_id("lyrics.generate")
        c.configure("image.generate", "image", {"prompt": "按歌词出图"}, lyr)
        c.run()
        c.finish_run()
        return c
    raise ValueError(f"unknown setup: {kind}")


TOOL_NAMES = {
    "configure_lyrics_workflow",
    "configure_image_workflow",
    "clear_workflow_draft",
    "read_workflow_state",
    "get_workflow_run_status",
    "wait_for_workflow_completion",
    "run_current_workflow",
}


def fake_tool_exec(canvas: FakeCanvas, name: str, args: dict) -> dict:
    """和生产同构的返回形状；桩的意义是让模型看到“真会拒绝”。可记录到轨迹。"""
    if name == "read_workflow_state":
        return canvas.to_summary()
    if name == "configure_lyrics_workflow":
        return canvas.configure(
            "lyrics.generate",
            "lyrics",
            {
                k: v
                for k, v in args.items()
                if k in ("theme", "style", "mood", "language")
            },
            args.get("upstream_node_id"),
        )
    if name == "configure_image_workflow":
        return canvas.configure(
            "image.generate",
            "image",
            {
                k: v
                for k, v in args.items()
                if k in ("prompt", "style", "ratio", "palette")
            },
            args.get("upstream_node_id"),
        )
    if name == "run_current_workflow":
        return canvas.run()
    if name == "get_workflow_run_status":
        running = [n for n in canvas.nodes if n.get("runStatus") == "running"]
        status = "running" if canvas.active_run else ("succeeded" if any(canvas.nodes) else "idle")
        return {
            "status": status,
            "run_id": "run-eval-1" if canvas.active_run else None,
            "progress": f"{len(canvas.nodes) - len(running)}/{len(canvas.nodes)}",
            "steps": [
                {"node": n["name"], "status": n.get("runStatus")} for n in canvas.nodes
            ],
        }
    if name == "wait_for_workflow_completion":
        canvas.finish_run()
        return {
            "status": "succeeded",
            "message": "运行已结束，你可以继续配节点或重新运行。",
        }
    if name == "clear_workflow_draft":
        canvas.nodes = _base_draft()
        canvas.edges = []
        return {"status": "cleared", "message": "已清空画布。"}
    return {"status": "ok", "message": f"stub:{name}"}


# ---------------------------------------------------------------------------
# 评测驱动：真实模型 + 真实 prompt + 真实 tools schema + 假执行器
# ---------------------------------------------------------------------------


def run_turn(
    canvas: FakeCanvas,
    user_text: str,
    model: str,
    dry_run: bool,
    history: list[dict] | None = None,
) -> dict:
    """跑一轮 ReAct（生产同款消息构筑）并返回轨迹。history 可注入历史污染场景。"""
    prompt = build_system_prompt(profile="", context="")
    tools_schema = _tools_for_context(False)
    messages = [{"role": "system", "content": prompt}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_text})
    calls: list[dict] = []
    reply_text = ""

    for _round in range(MAX_ROUNDS):
        if dry_run:
            # mock：静态映射，用来验证评测器自身功能
            planned = [{"name": "configure_lyrics_workflow", "arguments": {"theme": "mock"}}]
            # 只跑一次 configure 就收
            name = planned[0]["name"]
            result = fake_tool_exec(canvas, name, planned[0]["arguments"])
            calls.append({"name": name, "ok": True, "result": result})
            reply_text = "[dry]完成"
            break

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_schema,
            stream=False,
        )
        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []
        content = getattr(message, "content", "") or ""

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = fake_tool_exec(canvas, tc.function.name, args)
                calls.append({"name": tc.function.name, "args": args, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False),
                        "tool_call_id": tc.id,
                    }
                )
            continue

        reply_text = content
        break

    return {"calls": calls, "reply": reply_text}


# ---------------------------------------------------------------------------
# 断言
# ---------------------------------------------------------------------------

SIDE_EFFECT_TOOLS = {
    "configure_lyrics_workflow",
    "configure_image_workflow",
    "run_current_workflow",
    "clear_workflow_draft",
}


def assert_case(case: dict, trace: dict, canvas: FakeCanvas) -> list[str]:
    """返回失败原因列表；空列表 = 通过。"""
    errors: list[str] = []
    name_seq = [c["name"] for c in trace["calls"]]

    must = case.get("must_in_order")
    if must is not None:
        # 子序列匹配：允许模型在中间穿插 read/status 这类观察工具
        it = iter(name_seq)
        idx = 0
        for n in it:
            if n == must[idx]:
                idx += 1
                if idx == len(must):
                    break
        if idx < len(must):
            errors.append(f"序列不符，期望按序包含 {must}，实际为 {name_seq}")

    if case.get("must_call_any_of") and not any(n in name_seq for n in case["must_call_any_of"]):
            errors.append(f"应至少调用 {case['must_call_any_of']} 之一，实际为 {name_seq}")

    for forbidden in case.get("must_not", []):
        if forbidden in name_seq:
            errors.append(f"调用了禁用的工具: {forbidden}")

    if case.get("expect_no_side_effect"):
        side_calls = [n for n in name_seq if n in SIDE_EFFECT_TOOLS]
        if side_calls:
            errors.append(f"场景要求澄清/确认，但执行了有副作用的工具: {side_calls}")

    if case.get("extra_assert") == "image_has_upstream":
        # 断言：连线把 image 接到了 lyrics 后面（不是 Input）
        image_id = canvas.latest_capability_id("image.generate")
        ok = image_id is not None and any(
            e["target"] == image_id and e["source"] != "workflow-input" for e in canvas.edges
        )
        if not ok:
            errors.append(f"图像节点未被串联（实际 edges={canvas.edges}）")

    if case.get("extra_assert") == "image_no_upstream_ref":
        # 并联口吻下，图像不应引用上游结果
        image_id = canvas.latest_capability_id("image.generate")
        image_node = next((n for n in canvas.nodes if n["id"] == image_id), None)
        prompt = (image_node or {}).get("params", {}).get("prompt", "")
        if ".result.content}" in prompt:
            errors.append(f"并联口吻下图像节点仍引用了上游结果: {prompt}")

    return errors


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="mock 模型，仅验证评测器")
    parser.add_argument("--only", default=None, help="只跑名字包含该子串的用例")
    parser.add_argument("--repeat", type=int, default=1, help="每条用例重复次数（生成模型有随机性）")
    args = parser.parse_args()

    from core import config

    model = config.CHAT_MODEL
    if not args.dry_run and client is None:
        print("未配置 API_KEY，无法跑真模型评测", file=sys.stderr)
        return 2

    results = []
    total = 0
    passed = 0
    for case in CASES:
        if args.only and args.only not in case["name"]:
            continue
        for attempt_no in range(args.repeat):
            canvas = setup_canvas(case["setup"])
            started = time.perf_counter()
            trace = run_turn(canvas, case["user"], model, args.dry_run, case.get("history"))
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            errors = assert_case(case, trace, canvas)
            ok = not errors
            total += 1
            passed += int(ok)
            results.append(
                {
                    "name": case["name"],
                    "attempt": attempt_no + 1,
                    "user": case["user"],
                    "ok": ok,
                    "errors": errors,
                    "calls": [(c["name"], c.get("args", None)) for c in trace["calls"]],
                    "reply": trace["reply"][:160],
                    "duration_ms": duration_ms,
                }
            )
            mark = "PASS" if ok else "FAIL"
            suffix = f" #{attempt_no + 1}" if args.repeat > 1 else ""
            print(f"[{mark}] {case['name']}{suffix}  ({duration_ms}ms)")
            for e in errors:
                print(f"      - {e}")

    rate = (passed / total * 100) if total else 0.0
    print(f"\n==== 意图评测结果: {passed}/{total} 通过（{rate:.0f}%） ====")
    out = {
        "meta": {
            "model": model,
            "dry_run": args.dry_run,
            "case_count": total,
            "pass_count": passed,
            "pass_rate": rate,
        },
        "cases": results,
    }
    out_file = DRY_RESULT_FILE if args.dry_run else RESULT_FILE
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {out_file.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
