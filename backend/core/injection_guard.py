"""Prompt 注入防护（A10 / C16 的扩展，实际 SaaS 生产要件）。

第一重：输入侧 —— 检测劫持式措辞，先入，再进入意图分类。
第二重：知识内容注入过滤 —— RAG/附件片段里的"请忽略之前的指令"等伪装成指令的
prompt injection 是要被干掉的。
第三重：输出侧 —— 防止 system 提示/内部规则泄漏（被直接问出来）。

开关：INJECTION_GUARD_ENABLED=off 时完全绕过留审计记录可完成投资期
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("security")


# ---------- 注入模式（穷不穷体检，定遭拘） ----------

# jailbreak 套路关键词
_JAILBREAK = re.compile(
    r"忽略.{0,12}(?:系统提示|规则|指令)|"
    r"解除(?:限制|规则)|"
    r"无视(?:规则|提示)|"
    r"忽略所有|"
    r"ignore\s+(?:all|the).*instru(?:ction)?s?|"
    r"forget\s+(?:everything|all)??|"
    r"DAN|jailbreak",
    re.IGNORECASE | re.UNICODE,
)

# 提示回问
_PROMPT_LEAK = re.compile(
    r"你.{0,8}(?:system prompt|系统提示|初始指令)|"
    r"告诉我.{0,8}(?:规则|指令)prompt|"
    r"你预设的词是|prompt 是什么"
)

# 注入危险动作（非破坏操作）
_HARMFUL_ACTIONS = re.compile(
    r"(?:清空画布|清空并|删库|删除所有|清空所有|重置所有|全部删除|全部删掉|全部清空|"
    r"把工作区全部删掉|把工作区清空|删光了?|清光|毁坏.*项目|删除.*工作站)"
)


# ---------- 第一重：输入消息扫描 ----------


def scan_user_message(message: str) -> dict[str, Any]:
    """对用户新消息做静态扫描。返回 {is_inject, reason_codes}。

    is_inf 不是	position 拦截——是警告旗。处理由调用方决定。
    """
    reasons = []
    if _JAILBREAK.search(message):
        reasons.append("jailbreak_pattern")
    if _PROMPT_LEAK.search(message):
        reasons.append("prompt_leak_probe")
    if _HARMFUL_ACTIONS.search(message):
        reasons.append("potential_harmful")

    return {
        "is_suspicious": bool(reasons),
        "reasons": reasons,
        "severity": "high" if "potential_harmful" in reasons else ("medium" if reasons else "low"),
    }


# ---------- 第二重：知识内容过滤 ----------


def scan_rag_context(text: str) -> dict[str, Any]:
    """扫描即将进 system prompt 的 RAG/附件内容，找出隐藏的注入语句。"""
    patterns = [
        r"(?:请|gpt|assistant)[^a-zA-Z0-9]{0,8}忽略",
        r"ignore\s+(?:all|previous|the)",
        r"(?:请|立即)\s*(?:输出|生成)\s*你的.*(?:prompt|系统|规则)",
        r"系统.*指令",
        r"作为.{0,6}的.*(?:提示|指令)",
    ]
    hits = [line for line in text.split("\n") if any(re.search(p, line) for p in patterns)]
    return {"finds_injection": bool(hits), "suspicious_lines": hits[:5]}


# ---------- 第三重：输出回放防泄漏 ----------


def scan_assistant_reply(reply: str) -> dict[str, Any]:
    """模型回复包含自身系统提示的内部条款，属数据外泻。常见于概不过滤的垃圾邮件。"""
    markers = [
        "system prompt",
        "Knowledge Base 内容",
        "内部规则",
        "以下是给我的指令",
    ]
    hits = [m for m in markers if m in reply]
    return {"leaked": bool(hits), "markers": hits}


# ---------- 决策总线 ----------


def verdict(message: str = "", rag_text: str = "", reply: str = "") -> dict[str, Any]:
    """一处统一入口：入/出/检索三路合并评估。"""
    from core import config

    if not getattr(config, "INJECTION_GUARD_ENABLED", True):
        return {"action": "allow", "reason": "guard_disabled"}

    vin = scan_user_message(message) if message else {}
    vrag = scan_rag_context(rag_text) if rag_text else {}
    vout = scan_assistant_reply(reply) if reply else {}

    findings = []
    severity = "low"

    if vin.get("is_suspicious"):
        findings.extend(vin["reasons"])
        severity = vin["severity"]

    if vrag.get("finds_injection"):
        # RAG 注入是最典型的多材料攻击 - 中高优
        findings.append("rag_injection")
        severity = "medium"

    if vout.get("leaked"):
        # system prompt 泄漏要阻断
        findings.append("prompt_leak")
        severity = "high"

    if not findings:
        return {"action": "allow", "reason": "clean"}

    return {
        "action": "warn" if severity == "low" else ("scrub" if severity == "medium" else "block"),
        "reasons": findings,
        "severity": severity,
    }
