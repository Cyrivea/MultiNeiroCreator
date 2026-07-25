from typing import List

from pydantic import BaseModel, Field


class ChatAttachment(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: str | None = None
    badge: str | None = None
    meta: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str
    attachments: List[ChatAttachment] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    project_id: int | None = None
    attachments: List[ChatAttachment] = Field(default_factory=list)


class ProfileRequest(BaseModel):
    profile: str


class RagDocumentDeleteRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    project_id: int | None = None
