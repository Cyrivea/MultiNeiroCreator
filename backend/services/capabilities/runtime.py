"""Capability Runtime：统一承接用户直接运行、Assistant 和未来 Workflow。

能力清单收在一张注册表里：每条 entry 给出输入 Schema、执行器和对外展示名。
新增 Block = 在 ``CAPABILITY_REGISTRY`` 里追加一条，路由/工具/日志都复用。
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from schemas.capability import CapabilityResult
from services.capabilities.zhipu_text import ModelNotConfiguredError

logger = logging.getLogger("capabilities")


@dataclass(frozen=True)
class CapabilityContext:
    user_id: int
    project_id: int | None
    source: str


@dataclass(frozen=True)
class CapabilityEntry:
    capability_id: str
    display_name: str
    input_model: type[BaseModel]
    executor: Callable[[BaseModel], str]


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


def _lyrics_executor(inputs: BaseModel) -> str:
    from schemas.capability import LyricsGenerateInput
    from services.capabilities.zhipu_text import generate_lyrics_text

    assert isinstance(inputs, LyricsGenerateInput)
    return generate_lyrics_text(inputs)


def _image_executor(_inputs: BaseModel) -> str:
    """图像能力暂未接 Provider；返回模型未配置态而不是伪造一张图。"""
    raise ModelNotConfiguredError("图像模型尚未配置")


def _register() -> dict[str, CapabilityEntry]:
    from schemas.capability import ImageGenerateInput, LyricsGenerateInput

    return {
        "lyrics.generate": CapabilityEntry(
            capability_id="lyrics.generate",
            display_name="歌词",
            input_model=LyricsGenerateInput,
            executor=_lyrics_executor,
        ),
        "image.generate": CapabilityEntry(
            capability_id="image.generate",
            display_name="图像",
            input_model=ImageGenerateInput,
            executor=_image_executor,
        ),
    }


CAPABILITY_REGISTRY: dict[str, CapabilityEntry] = _register()


async def run_capability(
    capability_id: str,
    inputs: dict[str, Any],
    *,
    context: CapabilityContext,
) -> CapabilityResult:
    """执行一个受控生产能力，Provider 细节不向调用入口泄露。"""
    entry = CAPABILITY_REGISTRY.get(capability_id)
    if entry is None:
        return CapabilityResult(capability_id=capability_id, status="failed", error="不支持的生产能力")

    try:
        validated = entry.input_model.model_validate(inputs)
    except ValidationError:
        return CapabilityResult(
            capability_id=capability_id,
            status="failed",
            error=f"{entry.display_name}参数不符合平台要求",
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
        content = await asyncio.to_thread(entry.executor, validated)
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
            error=f"{entry.display_name}模型尚未配置，请稍后再试",
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
            error=f"{entry.display_name}生成失败，请稍后重试",
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
