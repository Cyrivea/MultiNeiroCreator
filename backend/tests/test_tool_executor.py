"""tool_executor 的单元测试（C2 拆分的直接收益）。

上帝函数时代，这些行为只能靠 mock 整条 SSE 流才能触达；
拆出 execute_tool 后，喂参数看结果单就行。
核心合同：**永不向外抛异常**，三种结局都是 ToolOutcome。
"""

import asyncio

from services.chat import tool_executor
from services.chat.tool_executor import ToolOutcome, execute_tool


def run(coro):
    return asyncio.run(coro)


def test_success_returns_ok_outcome():
    outcome = run(execute_tool("calculate", '{"expression": "1+2*3"}'))
    assert isinstance(outcome, ToolOutcome)
    assert outcome.ok is True
    assert "7" in outcome.result


def test_unknown_tool_rejected():
    outcome = run(execute_tool("rm_rf_root", "{}"))
    assert outcome.ok is False
    assert "不支持的工具" in outcome.result


def test_malformed_json_rejected():
    outcome = run(execute_tool("calculate", "{这不是json"))
    assert outcome.ok is False
    assert "解析失败" in outcome.result


def test_non_dict_args_rejected():
    outcome = run(execute_tool("calculate", '["列表", "不是字典"]'))
    assert outcome.ok is False
    assert "格式错误" in outcome.result


def test_oversized_arg_rejected():
    huge = "9" * (tool_executor.MAX_TOOL_ARG_LENGTH + 1)
    outcome = run(execute_tool("calculate", f'{{"expression": "{huge}"}}'))
    assert outcome.ok is False
    assert "过长" in outcome.result


def test_tool_exception_becomes_outcome_not_raise(monkeypatch):
    """合同的核心条款：工具内部炸了，调用方拿到的仍是结果单而不是异常。"""

    class BoomTool:
        def invoke(self, args):
            raise RuntimeError("boom")

    monkeypatch.setitem(tool_executor.tools_map, "calculate", BoomTool())
    outcome = run(execute_tool("calculate", '{"expression": "1"}'))
    assert outcome.ok is False
    assert "工具执行失败" in outcome.result


def test_tool_timeout_becomes_outcome_not_raise(monkeypatch):
    """防卡死：工具超过 TOOL_TIMEOUT_SECONDS 必须返回失败结果单而不是永远等待。"""

    class SlowTool:
        def invoke(self, args):
            import time

            time.sleep(3)
            return "never"

    monkeypatch.setitem(tool_executor.tools_map, "calculate", SlowTool())
    monkeypatch.setattr(tool_executor.config, "TOOL_TIMEOUT_SECONDS", 0.2)
    outcome = run(execute_tool("calculate", '{"expression": "1"}'))
    assert outcome.ok is False
    assert "超时" in outcome.result
