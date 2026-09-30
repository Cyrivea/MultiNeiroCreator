from datetime import UTC, datetime

from repositories import project_repo
from schemas.project import Project

# 工程文件由前端写入用户本地磁盘，后端只维护项目花名册；
# project_path 仅作展示标签，后端不做任何文件操作。
# 建表/索引由 core/migrations.py 在启动时完成（C9），SQL 全在 project_repo（C6）。


def list_recent_projects(user_id: int, limit: int = 8) -> list[Project]:
    return [Project(**dict(row)) for row in project_repo.list_recent(user_id, limit)]


def _now_timestamp() -> str:
    # 先取带时区的 UTC 再转本地，避免 naive datetime
    return datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def mark_project_saved(user_id: int, project_id: int) -> Project | None:
    """首次真实保存（自动保存写盘/用户显式保存）：面板准入打戳。"""
    row = project_repo.get_by_id(user_id, project_id)
    if row is None:
        return None
    project_repo.mark_saved(user_id, project_id, _now_timestamp())
    return get_project(user_id, project_id)


def discard_project(user_id: int, project_id: int) -> Project | None:
    """用户选「不保存」放弃从未保存过的工程：面板隐藏，磁盘文件不动（天然备份）。"""
    row = project_repo.get_by_id(user_id, project_id)
    if row is None:
        return None
    project_repo.discard(user_id, project_id, _now_timestamp())
    return get_project(user_id, project_id)


def touch_project_opened(user_id: int, project_id: int) -> Project | None:
    """真实打开：刷新 last_opened_at（修「面板按创建时间排」的旧 bug）+ 从放弃状态复活。"""
    row = project_repo.get_by_id(user_id, project_id)
    if row is None:
        return None
    project_repo.touch(user_id, project_id, _now_timestamp())
    return get_project(user_id, project_id)


def get_project(user_id: int, project_id: int) -> Project | None:
    row = project_repo.get_by_id(user_id, project_id)
    return Project(**dict(row)) if row else None


def create_project(user_id: int, name: str | None = None, project_path: str | None = None) -> Project:
    # 先取带时区的 UTC 再转本地，避免 naive datetime
    now = datetime.now(UTC).astimezone()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    project_name = _normalize_project_name(name, now)
    path_label = (project_path or "").strip()[:200] or "本地项目文件夹"

    project_id = project_repo.insert(user_id, project_name, path_label, "manual", timestamp)
    return Project(
        id=project_id,
        name=project_name,
        project_path=path_label,
        save_mode="manual",
        created_at=timestamp,
        updated_at=timestamp,
        last_opened_at=timestamp,
    )


def _normalize_project_name(name: str | None, now: datetime) -> str:
    cleaned = (name or "").strip()
    if cleaned:
        return cleaned[:120]
    return f"未命名项目 {now.strftime('%Y%m%d-%H%M%S')}"
