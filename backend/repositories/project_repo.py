"""projects 表的唯一 SQL 出入口（C6）：service 层只谈业务，不碰 SQL。"""

import sqlite3

from core.database import db_connection

_COLUMNS = "id, name, project_path, save_mode, created_at, updated_at, last_opened_at, saved_at, discarded_at"


def insert(user_id: int, name: str, project_path: str, save_mode: str, timestamp: str) -> int:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO projects"
            " (user_id, name, project_path, save_mode, created_at, updated_at, last_opened_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, project_path, save_mode, timestamp, timestamp, timestamp),
        )
        project_id = cursor.lastrowid
    assert project_id is not None  # INSERT 成功后 lastrowid 必有值
    return project_id


def list_recent(user_id: int, limit: int) -> list[sqlite3.Row]:
    # B29：面板 = 已保存且未放弃的项目，按真实打开时间排序（touch 负责刷新）
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            f"SELECT {_COLUMNS} FROM projects"
            " WHERE user_id=? AND saved_at IS NOT NULL AND discarded_at IS NULL"
            " ORDER BY datetime(last_opened_at) DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def mark_saved(user_id: int, project_id: int, timestamp: str) -> None:
    """首次真实保存打一次戳；已保存过则刷新时间（保留最早语义交给业务层，这里记录最新）。"""
    with db_connection() as conn:
        conn.execute(
            "UPDATE projects SET saved_at=?, updated_at=? WHERE user_id=? AND id=?",
            (timestamp, timestamp, user_id, project_id),
        )


def discard(user_id: int, project_id: int, timestamp: str) -> None:
    """软删除：面板隐藏但行保留（conversations/assets 按项目外键关联，硬删断链）。"""
    with db_connection() as conn:
        conn.execute(
            "UPDATE projects SET discarded_at=? WHERE user_id=? AND id=?",
            (timestamp, user_id, project_id),
        )


def touch(user_id: int, project_id: int, timestamp: str) -> None:
    """真实打开时刻刷新 + 从放弃状态复活（磁盘捡回工程 → 面板重新可见）。"""
    with db_connection() as conn:
        conn.execute(
            "UPDATE projects SET last_opened_at=?, discarded_at=NULL WHERE user_id=? AND id=?",
            (timestamp, user_id, project_id),
        )


def get_by_id(user_id: int, project_id: int) -> sqlite3.Row | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            f"SELECT {_COLUMNS} FROM projects WHERE user_id=? AND id=? LIMIT 1",
            (user_id, project_id),
        ).fetchone()
