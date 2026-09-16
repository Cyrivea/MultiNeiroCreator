"""真实 SQLite 集成测试（B23~B25 事故的直接防回归）。

与 test_workflow_service.py 的全 stub 单测互补：本文件把所有数据库操作
打在一份临时 SQLite 上跑完整生命周期——提交运行 → Worker 执行 →
步骤账本落库 → 状态查询 → 崩溃收尸。repositories 层不允许被 stub，
这正是生产事故('_step' KeyError、list_steps SQL 拼写错)钻过的空子。
"""


import pytest

import core.database as database
from core.migrations import run_migrations
from services import workflow_service
from services.workflow_service import finalize_failed_run, submit_workflow_run


@pytest.fixture
def real_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_FILE", db)
    run_migrations()
    return db


def _create_user(user_id: int) -> None:
    """workflow_drafts 有指向 users 的外键，真库测试必须先把用户建出来。"""
    with database.db_connection() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, profile, created_at) "
            "VALUES (?, ?, 'x', '', '2026-01-01')",
            (user_id, f"inttest-{user_id}@local"),
        )


def _configure_lyrics(user_id: int):
    return workflow_service.configure_lyrics(
        user_id, None, {"theme": "失恋", "style": "流行抒情", "mood": "忧郁、克制", "language": "中文"}
    )


def test_full_run_lifecycle_with_real_repos(real_db, monkeypatch):
    """提交 → 执行 → 步骤可见 → Draft 终态，全流程真库。"""
    from schemas.capability import CapabilityResult

    user = 900
    _create_user(user)
    _configure_lyrics(user)

    async def fake_capability(capability_id, inputs, *, context):
        return CapabilityResult(
            capability_id=capability_id,
            status="succeeded",
            result={"format": "markdown", "content": "测试歌词正文"},
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)

    submission = submit_workflow_run(user, None)
    assert submission["status"] == "queued"

    # 驱动 Worker  handler 同款入口（asyncio.run 装进同步函数）
    result = workflow_service.execute_workflow_run_job(
        job_id="job-test",
        run_id=submission["run_id"],
        draft_snapshot=submission["draft"],
        user_id=user,
        project_id=None,
    )
    assert result["status"] == "succeeded"

    # 运行步骤账本落库真实可查（此前 list_steps 拼坏 SQL 的地方）
    detail = workflow_service.get_run_status_detail(user, None, submission["run_id"])
    assert detail["status"] == "succeeded"
    assert detail["progress"] == {"done": 1, "total": 1}
    assert detail["steps"][0]["status"] == "succeeded"
    assert detail["steps"][0]["node_name"] == "歌词生成"

    # Draft 画布节点终态 = succeeded
    final = workflow_service.get_draft(user, None)
    node = next(n for n in final["draft"]["nodes"] if n.get("capability_id"))
    assert node["runStatus"] == "succeeded"
    assert node["result"]["content"] == "测试歌词正文"


def test_crash_finalization_releases_lock(real_db):
    """收尸：运行中断后 running 变 failed，编辑锁据 active=run 判定解除。"""
    user = 901
    _create_user(user)
    _configure_lyrics(user)
    submission = submit_workflow_run(user, None)

    # 人为卡住：把 running_draft 落到库，再崩溃
    finalize_failed_run(user, None, submission["run_id"], "RuntimeError: boom")

    detail = workflow_service.get_run_status_detail(user, None, submission["run_id"])
    assert detail["status"] == "failed"
    draft = workflow_service.get_draft(user, None)["draft"]
    stuck = [n for n in draft["nodes"] if n.get("runStatus") == "running"]
    assert not stuck

    # 收尸后可以重新保存编辑（不再被 WORKFLOW_BUSY 顶住）
    current = workflow_service.get_draft(user, None)
    saved = workflow_service.save_draft(user, None, current["draft"], current["revision"])
    assert saved["revision"] == current["revision"] + 1


def test_configure_rejects_upstream_ref_without_wiring(real_db):
    """图像 prompt 引用上游但未连线，配置期就得拒，不能留到运行期才炸。"""
    from core.exceptions import AppError

    user = 902
    _create_user(user)
    _configure_lyrics(user)
    with pytest.raises(AppError) as exc:
        workflow_service.configure_image(
            user,
            None,
            {"prompt": "按歌词出图: ${workflow-node-lyrics-x.result.content}", "style": "电影概念艺术"},
        )
    assert exc.value.status_code == 422
    assert "串联" in exc.value.detail or "上游" in exc.value.detail


def test_usage_ledger_insert_roundtrip(real_db):
    """用量账本占位符/列清单一致性：曾在生产上 '13 values for 12 columns' 静默丢账。"""
    from repositories import usage_repo

    _create_user(904)
    row = usage_repo.insert(
        904, None, "lyrics.generate", "workflow", "glm-4-flash",
        10, 20, 30, "succeeded", None, 12.5, "2026-09-16T09:00:00",
    )
    assert row["prompt_tokens"] == 10
    items = usage_repo.list_for_user(904)
    assert len(items) == 1 and items[0]["capability_id"] == "lyrics.generate"


def test_upstream_ref_normalized_when_wired(real_db):
    """模型自造的 ${workflow-node-xxx.result.content} 会被归一化成规范引用。"""
    user = 903
    _create_user(user)
    lyrics = _configure_lyrics(user)
    image = workflow_service.configure_image(
        user,
        None,
        {"prompt": "按歌词出图: ${workflow-node-x.result.content}", "style": "二次元插画"},
        upstream_node_id=lyrics["node_id"],
    )
    image_node = next(
        n for n in image["draft"]["nodes"] if n.get("capability_id") == "image.generate"
    )
    assert image_node["params"]["prompt"].endswith("${upstream.result.content}")
    edges = {(e["source"], e["target"]) for e in image["draft"]["edges"]}
    assert (lyrics["node_id"], image_node["id"]) in edges
