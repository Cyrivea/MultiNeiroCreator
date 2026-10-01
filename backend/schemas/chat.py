from pydantic import BaseModel, Field, model_validator

from core import config


class ChatAttachment(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: str | None = Field(default=None, max_length=100)
    badge: str | None = Field(default=None, max_length=100)
    meta: str | None = Field(default=None, max_length=255)


class ChatRequest(BaseModel):
    # 注意：不接收 history——对话历史以服务端数据库为唯一真源（A5），客户端多传的字段会被忽略
    message: str = Field(..., max_length=config.CHAT_MESSAGE_MAX_CHARS)
    project_id: int | None = None
    attachments: list[ChatAttachment] = Field(
        default_factory=list, max_length=config.CHAT_ATTACHMENTS_MAX_ITEMS
    )
    # 重生成模式（前端消息操作栏）：为 True 时先截断数据库尾轮（user+assistant），
    # 再按本次 message 正常落库——防同一问题在历史里重复堆叠（UI1）
    regenerate: bool = False


class ProfileRequest(BaseModel):
    profile: str = Field(..., max_length=config.PROFILE_MAX_CHARS)


class RagDocumentDeleteRequest(BaseModel):
    document_id: str | None = Field(default=None, min_length=32, max_length=32)
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    project_id: int | None = None

    @model_validator(mode="after")
    def require_document_identity(self):
        if not self.document_id and not self.filename:
            raise ValueError("document_id 或 filename 至少提供一个")
        return self
