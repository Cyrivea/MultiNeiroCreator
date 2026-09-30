import os
import sqlite3

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from core import database, migrations
from repositories import user_repo
from services import project_service


def test_get_project_returns_owner_project(tmp_path, monkeypatch):
    # 连接入口已统一到 core.database（C8），测试库重定向也改在这里
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "projects.db")
    # 建表统一走迁移（C9）；外键已生效，项目必须挂在真实用户下
    migrations.run_migrations()
    owner_id = user_repo.create_user("owner@test.com", "x")
    other_id = user_repo.create_user("other@test.com", "x")

    created = project_service.create_project(owner_id, "Alpha", "Folder Alpha")

    loaded = project_service.get_project(owner_id, created.id)
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.name == "Alpha"
    assert loaded.project_path == "Folder Alpha"

    assert project_service.get_project(other_id, created.id) is None


def test_migrations_idempotent_and_fk_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "mig.db")
    migrations.run_migrations()
    migrations.run_migrations()  # 幂等：重复执行不报错、版本不乱

    with database.db_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(migrations.MIGRATIONS)

    # 外键真的在管事：挂在不存在用户下的项目插不进去
    with pytest.raises(sqlite3.IntegrityError):
        project_service.create_project(99999, "Ghost", "nowhere")


def test_migration_upgrades_legacy_db(tmp_path, monkeypatch):
    """存量库（旧结构 + 孤儿数据）跑迁移：结构补齐、孤儿被清、数据保留。"""
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO users (username, password_hash) VALUES ('u@test.com', 'x');
        INSERT INTO messages (user_id, role, content) VALUES (1, 'user', 'hello');
        INSERT INTO messages (user_id, role, content) VALUES (999, 'user', 'orphan');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "DB_FILE", db_file)
    migrations.run_migrations()

    with database.db_connection() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        assert {"project_id", "attachments_json"} <= cols  # 旧库补列成功
        rows = conn.execute("SELECT user_id, content FROM messages").fetchall()
        assert rows == [(1, "hello")]  # 孤儿消息被清、正常数据保留


def test_panel_semantics_lifecycle(tmp_path, monkeypatch):
    """B29：面板 = 已保存且未放弃；从未保存被放弃的工程从面板消失且 404。"""
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "panel.db")
    migrations.run_migrations()
    user_id = user_repo.create_user("panel@test.com", "x")

    # 场景 1：新建即登记，但从未保存 → 不在面板
    never_saved = project_service.create_project(user_id, "草稿", "Folder A")
    assert project_service.list_recent_projects(user_id) == []

    # 场景 2：真实保存后 → 进面板
    project_service.mark_project_saved(user_id, never_saved.id)
    visible = project_service.list_recent_projects(user_id)
    assert [p.id for p in visible] == [never_saved.id]
    assert visible[0].saved_at is not None

    # 场景 3：保存过的工程被「不保存」放弃 → 只丢未保存修改，面板仍在（不该调 discard，
    # 但即使误调，touch 复活路径也验证下 discard 本身的行为）
    project_service.discard_project(user_id, never_saved.id)
    assert project_service.list_recent_projects(user_id) == []
    # 被放弃但保存过：GET 仍返回最后保存版本，/opened touch 可复活
    revived = project_service.get_project(user_id, never_saved.id)
    assert revived is not None and revived.saved_at is not None
    project_service.touch_project_opened(user_id, never_saved.id)
    assert [p.id for p in project_service.list_recent_projects(user_id)] == [never_saved.id]

    # 场景 4：从未保存 + 被放弃 → 彻底失效（业务层判据：saved_at is None）
    ghost = project_service.create_project(user_id, "幻影", "Folder B")
    project_service.discard_project(user_id, ghost.id)
    assert [p.id for p in project_service.list_recent_projects(user_id)] == [never_saved.id]
    assert project_service.get_project(user_id, ghost.id) is not None  # 行还在（软删除）
    assert project_service.get_project(user_id, ghost.id).saved_at is None  # 失效判据


def test_touch_updates_last_opened_ordering(tmp_path, monkeypatch):
    """B29 顺手修旧 bug：last_opened_at 从此真实刷新，面板按打开时间排序。"""
    import sqlite3 as _sq

    monkeypatch.setattr(database, "DB_FILE", tmp_path / "touch.db")
    migrations.run_migrations()
    user_id = user_repo.create_user("touch@test.com", "x")

    first = project_service.create_project(user_id, "先建", "F1")
    second = project_service.create_project(user_id, "后建", "F2")
    project_service.mark_project_saved(user_id, first.id)
    project_service.mark_project_saved(user_id, second.id)
    # 旧 bug：创建后 last_opened_at 不再更新，排序 = 创建顺序
    assert [p.id for p in project_service.list_recent_projects(user_id)] == [second.id, first.id]

    # 排除同秒平局干扰：把两个项目的 last_opened_at 都拨回过去，此时按 id DESC 排
    with _sq.connect(tmp_path / "touch.db") as raw:
        raw.execute(
            "UPDATE projects SET last_opened_at='2020-01-01 00:00:00'"
            " WHERE id IN (?, ?)",
            (first.id, second.id),
        )
    assert [p.id for p in project_service.list_recent_projects(user_id)] == [second.id, first.id]
    # 用户真实打开了 first → touch 刷新时间戳 → first 排到最前
    project_service.touch_project_opened(user_id, first.id)
    assert [p.id for p in project_service.list_recent_projects(user_id)] == [first.id, second.id]
