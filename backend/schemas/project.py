from pydantic import BaseModel, Field


class Project(BaseModel):
    """Project 的唯一业务定义（C5）：repo 行 → 本模型 → API 响应全链路同一形状。

    表结构（DDL）住在 core/migrations.py；这里是代码世界里 Project 长什么样的唯一答案，
    不再有手搓 dict 的第三种形状。
    """

    id: int
    name: str
    project_path: str
    save_mode: str = "manual"
    created_at: str
    updated_at: str
    last_opened_at: str
    # B29 面板语义：None = 从未真实保存过；非 None = 最近一次写盘时刻
    saved_at: str | None = None
    # None = 在面板可见；非 None = 被「不保存」放弃，面板隐藏（磁盘文件保留作备份）
    discarded_at: str | None = None


class CreateProjectRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    # 本地文件夹名，仅作展示标签使用，后端不会用它做任何文件操作
    project_path: str | None = Field(default=None, max_length=200)
