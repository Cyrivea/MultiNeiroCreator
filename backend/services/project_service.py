import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from core.config import DB_FILE, PROJECT_ROOT_DIR

WORKSPACE_PROJECTS_DIR = PROJECT_ROOT_DIR / "workspace" / "projects"


def init_projects_table() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            project_path TEXT NOT NULL,
            save_mode TEXT DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_opened_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def list_recent_projects(user_id: int, limit: int = 8) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, name, project_path, save_mode, created_at, updated_at, last_opened_at
        FROM projects
        WHERE user_id=?
        ORDER BY datetime(last_opened_at) DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "project_path": row["project_path"],
            "save_mode": row["save_mode"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_opened_at": row["last_opened_at"],
        }
        for row in rows
    ]


def create_project(user_id: int, name: Optional[str] = None) -> dict:
    init_projects_table()

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    project_name = _normalize_project_name(name, now)
    folder_name = _build_folder_name(project_name, now)
    project_dir = WORKSPACE_PROJECTS_DIR / folder_name

    WORKSPACE_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=False)

    for directory_name in ("assets", "audio", "image", "video", "exports"):
        (project_dir / directory_name).mkdir(exist_ok=True)

    project_meta = {
        "name": project_name,
        "created_at": timestamp,
        "updated_at": timestamp,
        "save_mode": "manual",
        "version": "0.1.0",
    }
    (project_dir / "project.json").write_text(
        json.dumps(project_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute(
        """
        INSERT INTO projects (user_id, name, project_path, save_mode, created_at, updated_at, last_opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            project_name,
            str(project_dir),
            "manual",
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()

    project = {
        "id": project_id,
        "name": project_name,
        "project_path": str(project_dir),
        "save_mode": "manual",
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_opened_at": timestamp,
    }

    project_meta["id"] = project_id
    (project_dir / "project.json").write_text(
        json.dumps(project_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return project


def ensure_project_for_auto_save(
    user_id: int,
    name: Optional[str] = None,
    project_path: Optional[str] = None,
    save_mode: str = "manual",
) -> dict:
    init_projects_table()

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    project_name = _normalize_project_name(name, now)
    project_dir = _resolve_or_create_project_dir(project_name, project_path, now)

    for directory_name in ("assets", "audio", "image", "video", "exports"):
        (project_dir / directory_name).mkdir(exist_ok=True)

    meta_file = project_dir / "project.json"
    project_meta = _read_project_meta(meta_file)

    if not isinstance(project_meta.get("name"), str) or not project_meta.get("name", "").strip():
        project_meta["name"] = project_name

    project_meta["created_at"] = project_meta.get("created_at") or timestamp
    project_meta["updated_at"] = timestamp
    project_meta["save_mode"] = save_mode
    project_meta["version"] = project_meta.get("version") or "0.1.0"

    meta_file.write_text(json.dumps(project_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_existing_project_save_mode(user_id, project_dir, save_mode, timestamp)

    return {
        "name": project_meta["name"],
        "project_path": str(project_dir),
        "save_mode": save_mode,
        "created_at": project_meta["created_at"],
        "updated_at": timestamp,
    }


def create_project_backup(
    user_id: int,
    name: Optional[str] = None,
    project_path: Optional[str] = None,
    save_mode: str = "manual",
) -> dict:
    project = ensure_project_for_auto_save(user_id, name=name, project_path=project_path, save_mode=save_mode)

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    file_timestamp = now.strftime("%Y%m%d_%H%M%S")
    project_dir = Path(project["project_path"])
    backup_dir = project_dir / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    meta_file = project_dir / "project.json"
    project_meta = _read_project_meta(meta_file)
    project_meta["name"] = project["name"]
    project_meta["updated_at"] = timestamp
    project_meta["save_mode"] = save_mode
    project_meta["last_backup_at"] = timestamp
    project_meta["version"] = project_meta.get("version") or "0.1.0"

    meta_file.write_text(json.dumps(project_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    backup_payload = {
        **project_meta,
        "backup_created_at": timestamp,
        "backup_source_path": str(project_dir),
    }
    backup_file = backup_dir / f"{_build_backup_file_name(project['name'], file_timestamp)}.json"
    backup_file.write_text(json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _sync_existing_project_save_mode(user_id, project_dir, save_mode, timestamp)

    return {
        "project": {
            **project,
            "updated_at": timestamp,
        },
        "backup_file": str(backup_file),
        "backup_created_at": timestamp,
    }


def _normalize_project_name(name: Optional[str], now: datetime) -> str:
    cleaned = (name or "").strip()
    if cleaned:
        return cleaned[:120]
    return f"未命名项目 {now.strftime('%Y%m%d-%H%M%S')}"


def _build_folder_name(project_name: str, now: datetime) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", project_name).strip(" .")
    safe_name = re.sub(r"\s+", "_", safe_name)
    safe_name = safe_name[:80] or "project"
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_name}_{uuid4().hex[:6]}"


def _resolve_or_create_project_dir(project_name: str, project_path: Optional[str], now: datetime) -> Path:
    if project_path:
        project_dir = Path(project_path)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    folder_name = _build_folder_name(project_name, now)
    WORKSPACE_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_dir = WORKSPACE_PROJECTS_DIR / folder_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _read_project_meta(meta_file: Path) -> dict:
    if not meta_file.exists():
        return {}

    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _sync_existing_project_save_mode(user_id: int, project_dir: Path, save_mode: str, timestamp: str) -> None:
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        UPDATE projects
        SET save_mode=?, updated_at=?
        WHERE user_id=? AND project_path=?
        """,
        (save_mode, timestamp, user_id, str(project_dir)),
    )
    conn.commit()
    conn.close()


def _build_backup_file_name(project_name: str, timestamp: str) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", project_name).strip(" .")
    safe_name = re.sub(r"\s+", "_", safe_name)
    safe_name = safe_name[:80] or "project"
    return f"{safe_name}_{timestamp}"
