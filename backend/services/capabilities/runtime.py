"""Capability Runtime：统一承接用户直接运行、Assistant 和未来 Workflow。"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from schemas.capability import CapabilityResult, LyricsGenerateInput
from services.capabilities.zhipu_text import ModelNotConfiguredError, generate_lyrics_text

logger = logging.getLogger("capabilities")


@dataclass(frozen=True)
class CapabilityContext:
    user_id: int
    project_id: int | None
    source: str


_capability_context: contextvars.ContextVar[CapabilityContext | None] = contextvars.ContextVar(
    "capability_context", default=None
)


def current_capability_context() -> CapabilityContext:
    return _capability_context.get() or CapabilityContext(user_id=0, project_id=None, source="assistant")


@contextlib.contextmanager
def use_capability_context(context: CapabilityContext) -> Iterator[None]:
    """在一次工具调用期间绑定隐藏的用户/项目上下文。"""
    token = _capability_context.set(context)
    try:
        yield
    finally:
        _capability_context.reset(token)


async def run_capability(
    capability_id: str,
    inputs: dict[str, Any],
    *,
    context: CapabilityContext,
) -> CapabilityResult:
    """执行一个受控生产能力，Provider 细节不向调用入口泄露。"""
    if capability_id != "lyrics.generate":
        return CapabilityResult(capability_id=capability_id, status="failed", error="不支持的生产能力")

    try:
        validated = LyricsGenerateInput.model_validate(inputs)
    except ValidationError:
        return CapabilityResult(
            capability_id=capability_id,
            status="failed",
            error="歌词参数不符合平台要求",
        )

    logger.info(
        "能力开始执行",
        extra={
            "evt": "capability_started",
            "capability": capability_id,
            "source": context.source,
            "user_id": context.user_id,
            "project_id": context.project_id,
        },
    )
    try:
        content = await asyncio.to_thread(generate_lyrics_text, validated)
    except ModelNotConfiguredError:
        logger.warning(
            "能力模型未配置",
            extra={
                "evt": "capability_model_unavailable",
                "capability": capability_id,
                "source": context.source,
            },
        )
        return CapabilityResult(
            capability_id=capability_id,
            status="model_unavailable",
            error="歌词模型尚未配置，请稍后再试",
        )
    except Exception as exc:
        logger.exception(
            "能力执行失败",
            extra={
                "evt": "capability_error",
                "capability": capability_id,
                "source": context.source,
                "error_type": type(exc).__name__,
            },
        )
        return CapabilityResult(
            capability_id=capability_id,
            status="failed",
            error="歌词生成失败，请稍后重试",
        )

    logger.info(
        "能力执行完成",
        extra={
            "evt": "capability_done",
            "capability": capability_id,
            "source": context.source,
            "user_id": context.user_id,
            "project_id": context.project_id,
            "result_chars": len(content),
        },
    )
    return CapabilityResult(
        capability_id=capability_id,
        status="succeeded",
        result={"format": "markdown", "content": content},
    )
