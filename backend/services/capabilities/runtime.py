"""Capability Runtime：统一承接用户直接运行、Assistant 和未来 Workflow。

能力清单收在一张注册表里：每条 entry 给出输入 Schema、执行器和对外展示名。
新增 Block = 在 ``CAPABILITY_REGISTRY`` 里追加一条，路由/工具/日志都复用。
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from repositories import usage_repo
from schemas.capability import CapabilityResult
from services.capabilities.zhipu_text import ModelNotConfiguredError

logger = logging.getLogger("capabilities")


@dataclass(frozen=True)
class CapabilityContext:
    user_id: int
    project_id: int | None
    source: str
    # 本轮用户原话：供工具做上下文敏感的安全检查（如注入式清空）
    user_message: str = ""


@dataclass(frozen=True)
class CapabilityEntry:
    capability_id: str
    display_name: str
    input_model: type[BaseModel]
    executor: Callable[[BaseModel], Any]


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


async def _record_usage(
    capability_id: str,
    context: CapabilityContext,
    *,
    model: str | None,
    status: str,
    error: str | None,
    duration_ms: float,
    usage: dict | None = None,
) -> None:
    """把一次能力调用写入账本。账本落库失败不能阻塞生成主链路。"""
    if context.user_id is None:
        return
    try:
        await asyncio.to_thread(
            usage_repo.insert,
            context.user_id,
            context.project_id,
            capability_id,
            context.source,
            model,
            int(usage["prompt_tokens"]) if usage else 0,
            int(usage["completion_tokens"]) if usage else 0,
            int(usage["total_tokens"]) if usage else 0,
            status,
            error[:500] if error else None,
            duration_ms,
            datetime.now(UTC).isoformat(),
        )
    except Exception as exc:
        logger.warning(
            "用量记录写不进入处: %s",
            type(exc).__name__,
            extra={"evt": "usage_record_failed", "capability": capability_id},
        )


def _lyrics_executor(inputs: BaseModel) -> dict:
    """真实 Provider 返回 {"content", "usage"}，Runtime 中心记录用量。"""
    from schemas.capability import LyricsGenerateInput
    from services.capabilities.zhipu_text import generate_lyrics_text

    assert isinstance(inputs, LyricsGenerateInput)
    return generate_lyrics_text(inputs)


def _image_executor(inputs: BaseModel) -> dict:
    """真实图像 Provider（SiliconFlow Kolors）。没配 KEY 仍会走 ModelNotConfiguredError 支路。"""
    from schemas.capability import ImageGenerateInput
    from services.capabilities.siliconflow_image import generate_image

    assert isinstance(inputs, ImageGenerateInput)
    return generate_image(inputs)


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


async def _write_asset(asset: dict, context: CapabilityContext) -> None:
    """把一次 capability 产出的资产插进资产表（不阻塞主链路）。"""
    try:
        from repositories import asset_repo

        await asyncio.to_thread(
            asset_repo.insert,
            user_id=context.user_id,
            project_id=context.project_id,
            run_id=None,
            capability_id=asset["capability_id"],
            kind="image",
            filename=asset["filename"],
            content_type="image/png",
            byte_size=0,
            prompt_snapshot=asset.get("prompt_snapshot"),
            usage_event_id=None,
            created_at=datetime.now(UTC).isoformat(),
        )
    except Exception as exc:
        logger.warning(
            "资产登记失败（不阻塞生成）",
            extra={"evt": "asset_register_failed", "error_type": type(exc).__name__},
        )


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
    started_at = time.perf_counter()
    try:
        output = await asyncio.to_thread(entry.executor, validated)
    except ModelNotConfiguredError:
        await _record_usage(
            capability_id,
            context,
            model=None,
            status="model_unavailable",
            error="模型尚未配置",
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )
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
        await _record_usage(
            capability_id,
            context,
            model=None,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )
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

    duration_ms = (time.perf_counter() - started_at) * 1000
    usage = output.get("usage") if isinstance(output, dict) else None
    content = output.get("content", "") if isinstance(output, dict) else output
    await _record_usage(
        capability_id,
        context,
        model=usage.get("model") if usage else None,
        status="succeeded",
        error=None,
        duration_ms=duration_ms,
        usage=usage,
    )

    # 用电资产登记账本：任何 capability 返回的 "asset" 字典会插入 assets 表
    asset = output.get("asset") if isinstance(output, dict) else None
    if asset:
        await _write_asset(asset, context)

    logger.info(
        "能力执行完成",
        extra={
            "evt": "capability_done",
            "capability": capability_id,
            "source": context.source,
            "user_id": context.user_id,
            "project_id": context.project_id,
            "result_chars": len(content or ""),
            "duration_ms": round(duration_ms, 1),
        },
    )
    return CapabilityResult(
        capability_id=capability_id,
        status="succeeded",
        result={"format": "markdown", "content": content},
    )
