"""重生成模式测试（UI1）：前后端同态的尾轮截断。

仓库层 pop_last_turn 在临时库里验证语义；编排层只验证调用时机与 409 拒绝路径。
"""

import asyncio
import json
import sqlite3

import pytest
from fastapi import HTTPException

import core.database
import services.chat.chat_orchestrator as chat_orchestrator
from repositories.chat_repo import list_history, pop_last_turn

# ---------- 仓库层：pop_last_turn 语义 ----------


MESSAGES_DDL = """
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    attachments_json TEXT,
    citations_json TEXT,
    interrupted INTEGER DEFAULT 0
)
"""


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """独立临时库：绝不碰生产 conversations.db（顺手给 C22 打了个样板）。"""
    db_file = tmp_path / "regen_test.db"
    monkeypatch.setattr(core.database, "DB_FILE", db_file)
    conn = sqlite3.connect(db_file)
    conn.execute(MESSAGES_DDL)
    conn.execute(
        "INSERT INTO messages (user_id, project_id, role, content) VALUES "
        "(1, 42, 'user', '第一问'), (1, 42, 'assistant', '第一答'),"
        "(1, 42, 'user', '第二问'), (1, 42, 'assistant', '旧答案')"
    )
    conn.commit()
    conn.close()
    return db_file


def test_pop_last_turn_truncates_user_plus_assistants(fresh_db):
    assert pop_last_turn(1, 42) is True
    roles = [item["role"] for item in list_history(1, 42)]
    assert roles == ["user", "assistant"]  # 只剩上一轮


def test_pop_last_turn_refuses_when_no_turn(fresh_db, tmp_path):
    assert pop_last_turn(999, 42) is False  # 别的用户不受影响
    rows = list_history(1, 42)
    assert [r["role"] for r in rows] == ["user", "assistant", "user", "assistant"]


def test_pop_last_turn_refuses_when_tail_has_notice(fresh_db):
    conn = sqlite3.connect(fresh_db)
    conn.execute(
        "INSERT INTO messages (user_id, project_id, role, content) "
        "VALUES (1, 42, 'system-notice', '工作流已完成')"
    )
    conn.commit()
    conn.close()
    assert pop_last_turn(1, 42) is False
    assert len(list_history(1, 42)) == 5  # 一条都没动


# ---------- 编排层：调用时机与拒绝路径 ----------


def content_stream(*texts):
    """与真实 SDK 同形状的假流：chunk.choices[0].delta.content。
    （初版只造了裸 delta，orchestrator 后来加了 `if not chunk.choices` 守卫后假件露馅）
    """

    class _Delta:
        def __init__(self, content):
            self.content = content
            self.tool_calls = None

    class _Choice:
        def __init__(self, delta):
            self.delta = delta

    class _Chunk:
        def __init__(self, content):
            self.choices = [_Choice(_Delta(content))]

    return [_Chunk(t) for t in texts]


class FakeClient:
    def __init__(self, script):
        self.calls = []
        self._script = list(script)
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self._script.pop(0))


def run_chat(user_message, regenerate):
    events = []

    async def collect():
        async for raw in chat_orchestrator.stream_chat(
            {"id": 1}, user_message, 42, regenerate=regenerate
        ):
            events.append(json.loads(raw.removeprefix("data: ").strip()))

    asyncio.run(collect())
    return events


def test_orchestrator_pops_before_building_context(monkeypatch):
    order = []
    monkeypatch.setattr(
        chat_orchestrator, "pop_last_turn", lambda uid, pid: order.append("pop") is None or True
    )

    async def fake_context(user_id, message, project_id=None, attachments=None):
        order.append("ctx")
        from services.chat.context_builder import ChatContext

        return ChatContext(
            messages=[{"role": "system", "content": "SYS"}, {"role": "user", "content": message}],
            clean_history=[{"role": "user", "content": message}],
            persist_text=message,
            attachments=[],
        )

    monkeypatch.setattr(chat_orchestrator, "build_chat_context", fake_context)
    monkeypatch.setattr(chat_orchestrator, "append_message", lambda *a, **kw: None)
    fake = FakeClient([content_stream("重写的答案")])
    monkeypatch.setattr(chat_orchestrator, "client", fake)

    events = run_chat("第二问", regenerate=True)

    assert order == ["pop", "ctx"]  # 先截库再重建上下文
    assert fake.calls, "重生成应该真的再调一次模型"
    done = [e for e in events if e["type"] == "done"]
    assert done and done[0]["history"][-1]["role"] == "assistant"


def test_orchestrator_409_when_nothing_to_regenerate(monkeypatch):
    monkeypatch.setattr(chat_orchestrator, "pop_last_turn", lambda uid, pid: False)
    fake = FakeClient([content_stream("不该被调用")])
    monkeypatch.setattr(chat_orchestrator, "client", fake)

    with pytest.raises(HTTPException) as exc_info:
        run_chat("问", regenerate=True)

    assert exc_info.value.status_code == 409
    assert not fake.calls, "拒绝路径绝不能真的去烧模型调用"


def test_orchestrator_normal_chat_never_pops(monkeypatch):
    called = []
    monkeypatch.setattr(
        chat_orchestrator, "pop_last_turn", lambda uid, pid: called.append(1) or True
    )

    async def fake_context(user_id, message, project_id=None, attachments=None):
        from services.chat.context_builder import ChatContext

        return ChatContext(
            messages=[{"role": "system", "content": "SYS"}, {"role": "user", "content": message}],
            clean_history=[{"role": "user", "content": message}],
            persist_text=message,
            attachments=[],
        )

    monkeypatch.setattr(chat_orchestrator, "build_chat_context", fake_context)
    monkeypatch.setattr(chat_orchestrator, "append_message", lambda *a, **kw: None)
    monkeypatch.setattr(chat_orchestrator, "client", FakeClient([content_stream("正常答案")]))

    run_chat("普通提问", regenerate=False)
    assert called == [], "普通对话绝不能触发尾轮截断"
