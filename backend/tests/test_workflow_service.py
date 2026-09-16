"""Workflow Draft 与歌词 Workflow Runner 的单元测试。

workflow_repo 的 SQLite 读写被替换成进程内字典——这里测的是 Draft 编排与
运行语义（节点创建/连线/参数校验/状态回流），SQLite 细节由 C9 迁移和仓库层负责。
"""

import asyncio
import copy
from typing import Any

import pytest

from core.exceptions import AppError
from schemas.capability import CapabilityResult
from services import workflow_service
from services.workflow_service import (
    INPUT_ID,
    OUTPUT_ID,
    configure_lyrics,
    run_workflow,
    save_draft,
)


class _RunRepoStub:
    """测试用 stub：active_run 非 None 时模拟“有运行正在进行”。"""

    def __init__(self, active_run=None, latest=None, steps=None):
        self._active = active_run
        self._latest = latest
        self._steps = steps or []

    def find_active_for_workflow(self, user_id, workflow_id):
        return self._active

    def list_recent(self, user_id, project_id, limit=5):
        return [self._latest] if self._latest else []

    def get(self, user_id, run_id):
        return self._latest if self._latest and self._latest["id"] == run_id else None

    def list_steps(self, user_id, run_id):
        return self._steps

    def create(self, **kwargs):
        return {"id": kwargs.get("run_id"), **kwargs}

    def create_step(self, **kwargs):
        return {"id": "step-stub"}

    def finish_step(self, *a, **k):
        return True

    def update_status(self, *a, **k):
        return True


@pytest.fixture
def memory_repo(monkeypatch):
    # run_repo 默认置空 stub：避免 save_draft 编辑锁检查误触真实 SQLite
    monkeypatch.setattr(workflow_service, "workflow_run_repo", _RunRepoStub())
    store: dict = {}

    def get(user_id, project_id):
        return copy.deepcopy(store.get((user_id, project_id)))

    def upsert(user_id, project_id, revision, draft, _timestamp):
        store[(user_id, project_id)] = {
            "id": 1,
            "revision": revision,
            "draft": copy.deepcopy(draft),
        }
        return copy.deepcopy(store[(user_id, project_id)])

    monkeypatch.setattr(workflow_service, "workflow_repo", _RepoStub(get, upsert))
    return store


class _RepoStub:
    def __init__(self, get, upsert):
        self.get = get
        self.upsert = upsert


def run(coro):
    return asyncio.run(coro)


def test_configure_creates_lyrics_node_with_edges(memory_repo):
    result = configure_lyrics(
        1,
        None,
        {"theme": "夏夜", "style": "城市民谣", "mood": "温柔、克制", "language": "中文"},
    )
    nodes = {n["id"]: n for n in result["draft"]["nodes"]}
    lyrics = result["node_id"]
    edges = {(e["source"], e["target"]) for e in result["draft"]["edges"]}

    assert result["revision"] == 1
    assert nodes[lyrics]["capability_id"] == "lyrics.generate"
    assert nodes[lyrics]["params"]["theme"] == "夏夜"
    assert (INPUT_ID, lyrics) in edges
    assert (lyrics, OUTPUT_ID) in edges


def test_configure_is_idempotent_and_updates_params(memory_repo):
    configure_lyrics(1, None, {"theme": "第一稿"})
    second = configure_lyrics(1, None, {"theme": "第二稿"})
    lyrics_nodes = [
        n for n in second["draft"]["nodes"] if n.get("capability_id") == "lyrics.generate"
    ]

    assert len(lyrics_nodes) == 1
    assert lyrics_nodes[0]["params"]["theme"] == "第二稿"
    assert second["revision"] == 2


def test_run_workflow_writes_result_back_to_node(memory_repo, monkeypatch):
    configure_lyrics(1, None, {"theme": "夏夜"})

    async def fake_capability(_capability_id, _inputs, *, context):
        assert context.source == "workflow"
        return CapabilityResult(
            capability_id="lyrics.generate",
            status="succeeded",
            result={"format": "markdown", "content": "# 夏夜\n主歌歌词"},
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)
    result = run(run_workflow(1, None))

    node = next(n for n in result["draft"]["nodes"] if n.get("capability_id"))
    assert node["runStatus"] == "succeeded"
    assert node["result"]["content"] == "# 夏夜\n主歌歌词"
    running_node = next(n for n in result["running_draft"]["nodes"] if n.get("capability_id"))
    assert running_node["runStatus"] == "running"  # running 快照先写库，终态再回流


def test_run_workflow_surfaces_model_unavailable(memory_repo, monkeypatch):
    configure_lyrics(1, None, {"theme": "夏夜"})

    async def fake_capability(*_args, **_kwargs):
        return CapabilityResult(
            capability_id="lyrics.generate",
            status="model_unavailable",
            error="歌词模型尚未配置，请稍后再试",
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)
    result = run(run_workflow(1, None))

    assert result["status"] == "model_unavailable"
    node = next(n for n in result["draft"]["nodes"] if n.get("capability_id"))
    assert node["runStatus"] == "model_unavailable"


def test_save_draft_rejects_stale_revision(memory_repo):
    configure_lyrics(1, None, {"theme": "夏夜"})
    current = workflow_service.get_draft(1, None)

    with pytest.raises(AppError) as exc:
        save_draft(1, None, current["draft"], expected_revision=current["revision"] - 1)
    assert exc.value.status_code == 409


def test_save_draft_rejects_invalid_edges(memory_repo):
    current = workflow_service.get_draft(1, None)
    bad = {**current["draft"], "edges": [{"source": "ghost", "target": OUTPUT_ID}]}

    with pytest.raises(AppError):
        save_draft(1, None, bad, expected_revision=current["revision"])


# ---------- 运行期编辑锁（B19）：运行中拒绝 Draft 写入，返回 WORKFLOW_BUSY ----------


def test_save_draft_rejected_while_run_active(memory_repo, monkeypatch):
    configure_lyrics(1, None, {"theme": "夏夜"})
    current = workflow_service.get_draft(1, None)
    monkeypatch.setattr(
        workflow_service,
        "workflow_run_repo",
        _RunRepoStub(active_run={"id": "run-busy", "status": "running"}),
    )

    with pytest.raises(AppError) as exc:
        save_draft(1, None, current["draft"], expected_revision=current["revision"])
    assert exc.value.status_code == 409
    assert "WORKFLOW_BUSY" in exc.value.detail


def test_save_draft_ok_when_no_active_run(memory_repo, monkeypatch):
    monkeypatch.setattr(workflow_service, "workflow_run_repo", _RunRepoStub())
    current = workflow_service.get_draft(1, None)
    saved = save_draft(1, None, current["draft"], expected_revision=current["revision"])
    assert saved["revision"] == current["revision"] + 1


def test_submit_run_rejected_when_already_running(memory_repo, monkeypatch):
    """已有运行进行时，重复提交直接拒绝，防止双跑互相覆盖候选与状态。"""
    monkeypatch.setattr(
        workflow_service,
        "workflow_run_repo",
        _RunRepoStub(active_run={"id": "run-busy", "status": "queued"}),
    )
    with pytest.raises(AppError) as exc:
        workflow_service.submit_workflow_run(1, None)
    assert exc.value.status_code == 409
    assert "WORKFLOW_BUSY" in exc.value.detail


# ---------- 运行状态查询（B18）：run_id 可省略，返回进度与节点明细 ----------


_RUN_FIXTURE = {
    "id": "run-abc",
    "user_id": 1,
    "project_id": None,
    "status": "failed",
    "error": "图像生成: 模型尚未配置",
    "created_at": "2026-09-16T00:00:00",
    "started_at": "2026-09-16T00:00:01",
    "finished_at": "2026-09-16T00:01:00",
    "draft_snapshot": {
        "nodes": [
            {"id": "node-lyr", "name": "歌词生成"},
            {"id": "node-img", "name": "图像生成"},
        ],
        "edges": [],
    },
}

_STEPS_FIXTURE = [
    {"id": "s1", "run_id": "run-abc", "node_id": "node-lyr", "capability_id": "lyrics.generate",
     "status": "succeeded", "input": None, "output": None, "error": None},
    {"id": "s2", "run_id": "run-abc", "node_id": "node-img", "capability_id": "image.generate",
     "status": "failed", "input": None, "output": None, "error": "模型尚未配置"},
]


def test_get_run_status_detail_returns_progress_and_steps(memory_repo, monkeypatch):
    monkeypatch.setattr(
        workflow_service,
        "workflow_run_repo",
        _RunRepoStub(latest=_RUN_FIXTURE, steps=_STEPS_FIXTURE),
    )
    detail = workflow_service.get_run_status_detail(1, None)
    assert detail["run_id"] == "run-abc"
    assert detail["status"] == "failed"
    assert detail["progress"] == {"done": 2, "total": 2}
    names = [step["node_name"] for step in detail["steps"]]
    assert names == ["歌词生成", "图像生成"]
    assert detail["steps"][1]["error"] == "模型尚未配置"


def test_get_run_status_detail_404_when_no_runs(memory_repo, monkeypatch):
    monkeypatch.setattr(workflow_service, "workflow_run_repo", _RunRepoStub())
    with pytest.raises(AppError) as exc:
        workflow_service.get_run_status_detail(1, None)
    assert exc.value.status_code == 404


# ---------- 崩溃收尸（防卡死）：运行中断后running 节点/运行状态必须复位成 failed ----------


def test_finalize_failed_run_resets_stuck_nodes(memory_repo):
    configure_lyrics(1, None, {"theme": "夏夜"})
    store = memory_repo
    draft = store[(1, None)]["draft"]
    for node in draft["nodes"]:
        if node.get("capability_id"):
            node["runStatus"] = "running"
    statuses = {}
    stub = _RunRepoStub()
    stub.update_status = lambda run_id, status, **kw: statuses.__setitem__(run_id, status) or True
    workflow_service.workflow_run_repo.update_status = stub.update_status

    workflow_service.finalize_failed_run(1, None, "run-stuck", "KeyError: boom")

    assert statuses["run-stuck"] == "failed"
    after = workflow_service.get_draft(1, None)
    for node in after["draft"]["nodes"]:
        if node.get("capability_id"):
            assert node["runStatus"] == "failed"
            assert "KeyError" in node["error"]


# ---------- 图像节点：API 不装也能搭建 Workflow，运行时如实上报模型未配置 ----------


def test_configure_image_creates_node(memory_repo):
    result = workflow_service.configure_image(
        1,
        None,
        {"prompt": "雨夜小店", "style": "电影概念艺术", "ratio": "16:9", "palette": "深蓝与紫色"},
    )
    nodes = {n["id"]: n for n in result["draft"]["nodes"]}
    image_node_id = result["node_id"]

    assert nodes[image_node_id]["capability_id"] == "image.generate"
    assert nodes[image_node_id]["type"] == "image"
    assert nodes[image_node_id]["params"]["prompt"] == "雨夜小店"
    edges = {(e["source"], e["target"]) for e in result["draft"]["edges"]}
    assert (INPUT_ID, image_node_id) in edges
    assert (image_node_id, OUTPUT_ID) in edges


def test_image_run_reports_model_not_configured(memory_repo):
    workflow_service.configure_image(1, None, {"prompt": "雨夜小店"})
    result = run(run_workflow(1, None))

    assert result["status"] == "model_unavailable"
    node = next(n for n in result["draft"]["nodes"] if n.get("capability_id") == "image.generate")
    assert node["runStatus"] == "model_unavailable"
    assert "尚未配置" in (node["error"] or "")


def test_workflow_rejects_unconfigured_capability(memory_repo):
    current = workflow_service.get_draft(1, None)
    draft = copy.deepcopy(current["draft"])
    draft["nodes"].append(
        {
            "id": "n-ghost",
            "kind": "tool",
            "capability_id": "video.generate",
            "name": "视频生成",
        }
    )
    draft["edges"].append({"source": INPUT_ID, "target": "n-ghost"})
    save_draft(1, None, draft, expected_revision=0)

    with pytest.raises(AppError) as exc:
        run(run_workflow(1, None))
    assert "未注册的能力" in exc.value.detail


# ---------- Runner 不能回写旧拓扑：运行期间的新连线不能被覆盖 ----------


def test_runner_never_overwrites_new_edges(memory_repo, monkeypatch):
    """用户在 Workflow 运行期间新建了连线；Runner 结束后不能把它抹掉。"""
    configure_lyrics(1, None, {"theme": "夏夜"})
    run_id = "run-race-1"

    captured_draft_states = []
    # Runner 执行期间，用户往画布上连了一条新边（模拟 AI 又改图或手拉线）
    current = workflow_service.get_draft(1, None)
    draft_with_extra_edge = copy.deepcopy(current["draft"])
    draft_with_extra_edge["edges"].append({"source": INPUT_ID, "target": OUTPUT_ID})
    save_draft(1, None, draft_with_extra_edge, expected_revision=current["revision"])

    monkeypatch.setattr(
        workflow_service.workflow_run_repo, "create_step", lambda **kw: {"id": "step-x"}
    )
    monkeypatch.setattr(workflow_service.workflow_run_repo, "finish_step", lambda *a, **k: True)
    monkeypatch.setattr(workflow_service.workflow_run_repo, "update_status", lambda *a, **k: True)

    async def fake_capability(capability_id, inputs, *, context):
        # 假装抓到此刻的真实 Draft——应该已经带上那条新边
        live = workflow_service.get_draft(user_id=1, project_id=None)
        captured_draft_states.append(copy.deepcopy(live["draft"]))
        return CapabilityResult(
            capability_id=capability_id,
            status="succeeded",
            result={"format": "markdown", "content": "歌词正文"},
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)
    out = workflow_service.execute_workflow_run_job(
        job_id="job-x", run_id=run_id, draft_snapshot=current["draft"], user_id=1, project_id=None
    )
    assert out["status"] == "succeeded"

    final = workflow_service.get_draft(1, None)["draft"]
    assert any(e["source"] == INPUT_ID and e["target"] == OUTPUT_ID for e in final["edges"]), (
        "Runner 必须不动 Draft 拓扑：运行期间新增的连线不能被覆盖"
    )


def test_chained_configure_rewires_edges(memory_repo):
    lyrics = configure_lyrics(1, None, {"theme": "夏夜"})
    lyrics_id = lyrics["node_id"]

    image = workflow_service.configure_image(
        1, None, {"prompt": "按歌词出图"}, upstream_node_id=lyrics_id
    )
    edges = {(e["source"], e["target"]) for e in image["draft"]["edges"]}
    image_id = image["node_id"]

    assert (INPUT_ID, image_id) not in edges          # 图像不再直接挂在 Input
    assert (INPUT_ID, lyrics_id) in edges
    assert (lyrics_id, image_id) in edges
    assert (image_id, OUTPUT_ID) in edges
    assert (lyrics_id, OUTPUT_ID) not in edges        # 链尾迁到图像节点


def test_chained_upstream_result_flows_into_downstream_params(memory_repo, monkeypatch):
    """歌词节点产出内容，经过 ${upstream.result.content} 进入图像节点输入。"""
    placeholder = "${upstream.result.content}"
    lyrics = configure_lyrics(1, None, {"theme": "夏夜"})
    lyrics_id = lyrics["node_id"]
    workflow_service.configure_image(
        1,
        None,
        {"prompt": f"根据歌词生成画面: {placeholder}"},
        upstream_node_id=lyrics_id,
    )

    captured: dict[str, Any] = {}

    async def fake_capability(capability_id, inputs, *, context):
        if capability_id == "lyrics.generate":
            return CapabilityResult(
                capability_id=capability_id,
                status="succeeded",
                result={"format": "markdown", "content": "夏夜歌词正文"},
            )
        captured["image_inputs"] = inputs
        return CapabilityResult(
            capability_id=capability_id,
            status="succeeded",
            result={"format": "markdown", "content": "mock image"},
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)
    result = run(run_workflow(1, None))

    assert "夏夜歌词正文" in captured["image_inputs"]["prompt"]
    assert placeholder not in captured["image_inputs"]["prompt"]
    final_nodes = {n["id"]: n for n in result["draft"]["nodes"]}
    assert final_nodes[lyrics_id]["runStatus"] == "succeeded"


def test_submit_run_enqueues_job_and_marks_nodes_running(memory_repo, monkeypatch):
    configure_lyrics(1, None, {"theme": "夏夜"})
    jobs = []
    runs = []
    monkeypatch.setattr(
        workflow_service.job_service,
        "create_job",
        lambda **kw: jobs.append(kw) or {"id": "job-1"},
    )
    monkeypatch.setattr(
        workflow_service.workflow_run_repo, "create", lambda **kw: runs.append(kw) or kw
    )
    result = workflow_service.submit_workflow_run(1, None)

    assert result["status"] == "queued"
    assert result["job_id"] == "job-1"
    assert jobs[0]["job_type"] == "workflow_run"
    assert jobs[0]["payload"]["run_id"] == result["run_id"]
    node = next(n for n in result["draft"]["nodes"] if n.get("capability_id"))
    assert node["runStatus"] == "running"


def test_execute_snapshot_run_writes_steps_and_statuses(memory_repo, monkeypatch):
    configure_lyrics(1, None, {"theme": "夏夜"})
    draft = copy.deepcopy(workflow_service.get_draft(1, None)["draft"])
    steps = []
    statuses = {}
    monkeypatch.setattr(
        workflow_service.workflow_run_repo,
        "create_step",
        lambda **kw: steps.append(kw) or {"id": f"step-{len(steps)}"},
    )
    monkeypatch.setattr(workflow_service.workflow_run_repo, "finish_step", lambda *a, **k: True)
    monkeypatch.setattr(
        workflow_service.workflow_run_repo,
        "update_status",
        lambda run_id, status, **kw: statuses.__setitem__(run_id, status) or True,
    )

    async def fake_capability(capability_id, inputs, *, context):
        return CapabilityResult(
            capability_id=capability_id,
            status="succeeded",
            result={"format": "markdown", "content": "歌词正文"},
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)
    out = workflow_service.execute_workflow_run_job(
        job_id="j", run_id="run-1", draft_snapshot=draft, user_id=1, project_id=None
    )

    assert out["status"] == "succeeded"
    assert statuses["run-1"] == "succeeded"
    assert steps[0]["node_id"]
    node = next(
        n for n in workflow_service.get_draft(1, None)["draft"]["nodes"] if n.get("capability_id")
    )
    assert node["runStatus"] == "succeeded"
    assert node["result"]["content"] == "歌词正文"


# ---------- 多版本候选：必须人工选择，不允许隐式随便挑一个 ----------


def test_rerun_appends_candidate_records(memory_repo, monkeypatch):
    configure_lyrics(1, None, {"theme": "夏夜"})

    async def fake_capability(capability_id, inputs, *, context):
        return CapabilityResult(
            capability_id=capability_id,
            status="succeeded",
            result={"format": "markdown", "content": "歌词版本"},
        )

    monkeypatch.setattr(workflow_service, "run_capability", fake_capability)
    run(run_workflow(1, None))
    run(run_workflow(1, None))

    node = next(
        n for n in workflow_service.get_draft(1, None)["draft"]["nodes"] if n.get("capability_id")
    )
    assert len(node["candidates"]) == 2
    assert node["selectedCandidateId"] == node["candidates"][0]["id"]


def test_multi_candidate_requires_manual_choice(memory_repo):
    """上游已有多个成功版本但没选定：占位符不能隐式拿任何一份，必须让用户选。"""
    configure_lyrics(1, None, {"theme": "夏夜"})
    current = workflow_service.get_draft(1, None)
    draft = current["draft"]
    node = next(n for n in draft["nodes"] if n.get("capability_id"))
    node["candidates"] = [
        {"id": "c-a", "status": "succeeded", "content": "版本 A", "created_at": workflow_service._now()},
        {"id": "c-b", "status": "succeeded", "content": "版本 B", "created_at": workflow_service._now()},
    ]
    save_draft(1, None, draft, expected_revision=current["revision"])

    # 再挂一个图像节点吃上游
    image = workflow_service.configure_image(
        1,
        None,
        {"prompt": "根据 ${upstream.result.content} 生成"},
        upstream_node_id=node["id"],
    )
    image_node = next(
        n for n in image["draft"]["nodes"] if n.get("capability_id") == "image.generate"
    )

    resolved, error = workflow_service._resolve_params(image_node, image["draft"], {})
    assert error is not None and "先在其中选一个" in error

    # 手动选版本后就能解析到选中的内容
    upstream_node = next(
        n for n in image["draft"]["nodes"] if n.get("capability_id") == "lyrics.generate"
    )
    upstream_node["selectedCandidateId"] = "c-b"
    resolved, error = workflow_service._resolve_params(image_node, image["draft"], {})
    assert error is None
    assert resolved["prompt"] == "根据 版本 B 生成"


def test_clear_workflow_resets_draft(memory_repo):
    configure_lyrics(1, None, {"theme": "夏夜"})
    cleared = workflow_service.clear_workflow(1, None)

    tool_nodes = [n for n in cleared["draft"]["nodes"] if n.get("kind") != "endpoint"]
    assert tool_nodes == []
    assert cleared["draft"]["edges"] == []
    assert cleared["revision"] == 2


def test_reconfigure_reuses_node_without_duplicates(memory_repo):
    workflow_service.configure_image(1, None, {"prompt": "第一次"})
    second = workflow_service.configure_image(1, None, {"prompt": "第二次"})

    images = [
        n for n in second["draft"]["nodes"] if n.get("capability_id") == "image.generate"
    ]
    assert len(images) == 1
    assert images[0]["params"]["prompt"] == "第二次"
    # 同一 capability 的入边仍只有 Input → 节点那一条
    inputs = [e for e in second["draft"]["edges"] if e["target"] == images[0]["id"]]
    assert len(inputs) == 1
