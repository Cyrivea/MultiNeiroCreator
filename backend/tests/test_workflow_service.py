"""Workflow Draft 与歌词 Workflow Runner 的单元测试。

workflow_repo 的 SQLite 读写被替换成进程内字典——这里测的是 Draft 编排与
运行语义（节点创建/连线/参数校验/状态回流），SQLite 细节由 C9 迁移和仓库层负责。
"""

import asyncio
import copy

import pytest

from core.exceptions import AppError
from schemas.capability import CapabilityResult
from services import workflow_service
from services.workflow_service import (
    INPUT_ID,
    OUTPUT_ID,
    configure_lyrics,
    run_lyrics_workflow,
    save_draft,
)


@pytest.fixture
def memory_repo(monkeypatch):
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
    result = run(run_lyrics_workflow(1, None))

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
    result = run(run_lyrics_workflow(1, None))

    assert result["result"].status == "model_unavailable"
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
