from typing import Optional

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    # 本地文件夹名，仅作展示标签使用，后端不会用它做任何文件操作
    project_path: Optional[str] = Field(default=None, max_length=200)
