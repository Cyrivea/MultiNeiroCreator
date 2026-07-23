from typing import List

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    project_id: int | None = None


class ProfileRequest(BaseModel):
    profile: str


class RagDocumentDeleteRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
