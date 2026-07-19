from typing import Optional

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)


class AutoSaveProjectRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    project_path: Optional[str] = Field(default=None, max_length=500)
    save_mode: str = Field(..., max_length=40)
