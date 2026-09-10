"""歌词生成 Block：只提供受控 Schema，真正执行统一交给 Capability Runtime。"""

from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool

from schemas.capability import LyricsGenerateInput, LyricsLanguage, LyricsMood, LyricsStyle
from services.capabilities import CapabilityContext, current_capability_context, run_capability

CAPABILITY_ID = "lyrics.generate"


@tool
async def generate_lyrics_block(
    theme: str,
    style: LyricsStyle = "流行抒情",
    mood: LyricsMood = "温柔、克制",
    language: LyricsLanguage = "中文",
    context: Annotated[dict[str, object] | None, InjectedToolArg] = None,
) -> str:
    """使用平台托管的歌词生成 Block，根据主题、曲风、情绪和语言生成歌词。

    Args:
        theme: 歌词主题，长度不能超过 200 个字符。
        style: 歌曲风格，只能选择平台支持的风格。
        mood: 歌词情绪，只能选择平台支持的情绪。
        language: 歌词语言，只能选择平台支持的语言。
    """
    inputs = LyricsGenerateInput(theme=theme, style=style, mood=mood, language=language)
    if context is None:
        execution_context = current_capability_context()
    else:
        execution_context = CapabilityContext(
            user_id=int(context.get("user_id", 0)),
            project_id=(
                int(context["project_id"]) if context.get("project_id") is not None else None
            ),
            source=str(context.get("source", "assistant")),
        )
    result = await run_capability(CAPABILITY_ID, inputs.model_dump(), context=execution_context)
    return result.model_dump_json(ensure_ascii=False)


# 模型可见 schema 只包含能力参数；InjectedToolArg 仍作为底层调用的隐藏参数保留。
generate_lyrics_block.args_schema = LyricsGenerateInput
