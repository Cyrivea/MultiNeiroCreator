"""生产能力请求与结果 Schema。"""

from typing import Literal

from pydantic import BaseModel, Field

LyricsStyle = Literal["流行抒情", "城市民谣", "电子流行", "摇滚叙事"]
LyricsMood = Literal["温柔、克制", "明亮、轻快", "忧郁、克制", "热烈、昂扬", "孤独、怀旧"]
LyricsLanguage = Literal["中文", "英文", "中英混合"]

ImageStyle = Literal["电影概念艺术", "二次元插画", "写实摄影", "复古胶片"]
ImageRatio = Literal["16:9", "1:1", "9:16", "4:3"]
ImagePalette = Literal["深蓝与紫色", "黑白", "暖金", "低饱和绿色", "高对比彩色"]


class LyricsGenerateInput(BaseModel):
    """歌词 Block 的受控输入；前后端和 Assistant 共用。"""

    theme: str = Field(..., min_length=1, max_length=200)
    style: LyricsStyle = "流行抒情"
    mood: LyricsMood = "温柔、克制"
    language: LyricsLanguage = "中文"


class ImageGenerateInput(BaseModel):
    """图像 Block 的受控输入；不接真实图片 API 时也必须具备同样的校验边界。"""

    prompt: str = Field(..., min_length=1, max_length=300)
    style: ImageStyle = "电影概念艺术"
    ratio: ImageRatio = "16:9"
    palette: ImagePalette = "深蓝与紫色"


class CapabilityRunRequest(BaseModel):
    """当前只开放歌词能力，后续按 capability_id 扩展而不是开放任意 Provider。"""

    capability_id: Literal["lyrics.generate"]
    project_id: int | None = None
    inputs: LyricsGenerateInput


class CapabilityResult(BaseModel):
    capability_id: str
    status: Literal["succeeded", "model_unavailable", "failed"]
    result: dict[str, str] | None = None
    error: str | None = None
