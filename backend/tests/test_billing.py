"""计费核心服务测试 —《计费与商业化方案.md》§7/§12 验收的机器化：

- 预占/结算在并发下不透支、不漏扣、不重复扣款；
- 历史费用引用调用时的价格版本，改价不影响旧账；
- 余额不足在上游调用前杜绝（enforce 模式 runtime 集成）；
- 预占在失败/取消/进程死路径都能被回收（release / sweep）。
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from core import database, migrations
from core.database import db_connection
from repositories import billing_repo, usage_repo
from services import billing_service


def now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture
def billing_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "billing.db")
    migrations.run_migrations()
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("billing-owner@example.com", "hash"),
        )
        user_id = conn.execute("SELECT id FROM users").fetchone()[0]
    billing_service.add_price_version("test-model", "1.0", "2.0", per_call_credits="0.5")
    return user_id


def _account(user_id: int) -> dict:
    with db_connection() as conn:
        account = billing_repo.get_account(conn, user_id)
    assert account is not None
    return account


def test_migration_creates_billing_tables(billing_db):
    with db_connection() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 13
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'credit_%' OR name LIKE 'model_%' OR name LIKE 'subscriptions'"
        )}
    assert {"credit_accounts", "credit_reservations", "credit_ledger", "subscriptions", "model_price_versions"} <= tables


def test_ledger_is_immutable(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    with db_connection() as conn, pytest.raises(Exception, match="不可变流水"):
        conn.execute("UPDATE credit_ledger SET amount_micro=999")
    with db_connection() as conn, pytest.raises(Exception, match="不可变流水"):
        conn.execute("DELETE FROM credit_ledger")


def test_grant_and_balance(billing_db):
    result = billing_service.grant_plan_credits(billing_db, "plus", Decimal("50"), 30)
    balance = billing_service.get_balance(billing_db)
    assert result["credits"] == "50"
    assert balance["plan_credits"] == "50.000000"
    assert balance["prepaid_credits"] == "0.000000"
    assert any(entry["type"] == "subscription_grant" for entry in balance["recent_ledger"])


def test_reserve_settle_releases_over_reserved(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    billing_service.reserve(billing_db, "resv:1", Decimal("5"))
    mid = _account(billing_db)
    assert mid["plan_available_micro"] == 5 * 1_000_000
    assert mid["plan_reserved_micro"] == 5 * 1_000_000

    # 真实用量：prompt 1000 + completion 500，按 1.0/2.0 每千 → 1 + 1 + 0.5 = 2.5 积分
    billed = billing_service.settle("resv:1", "test-model", 1000, 500)
    assert billed == Decimal("2.500000")
    final = _account(billing_db)
    assert final["plan_available_micro"] == 7_500_000  # 10 - 5 + 2.5 退回 - 2.5 扣
    assert final["plan_reserved_micro"] == 0


def test_settle_under_reserved_deducts_extra(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    billing_service.reserve(billing_db, "resv:2", Decimal("0.5"))
    # 真实用量是 5 积分：预占的 0.5 退不回，要再补扣 4.5
    billed = billing_service.settle("resv:2", "test-model", 3000, 1000)
    assert billed == Decimal("5.500000")  # 3×1.0 + 1×2.0 + 0.5 固定每次
    final = _account(billing_db)
    assert final["plan_available_micro"] == 4_500_000


def test_settle_is_idempotent(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    billing_service.reserve(billing_db, "resv:3", Decimal("5"))
    billing_service.settle("resv:3", "test-model", 1000, 500)
    again = billing_service.settle("resv:3", "test-model", 1000, 500)
    assert again == Decimal("2.500000")
    # 只记一次结算
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM credit_ledger WHERE reference_id='resv:3' AND type='usage_release'"
        ).fetchone()
    assert rows[0] == 1
    assert _account(billing_db)["plan_available_micro"] == 7_500_000


def test_settle_unknown_reference_raises(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    with pytest.raises(billing_service.ReservationNotFoundError):
        billing_service.settle("resv:never", "test-model", 0, 0)


def test_insufficient_reject_without_touching_account(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("2"), 30)
    with pytest.raises(billing_service.InsufficientCreditsError):
        billing_service.reserve(billing_db, "resv:poor", Decimal("5"))
    assert _account(billing_db)["plan_available_micro"] == 2_000_000


def test_concurrent_reserve_never_oversells(billing_db):
    """10 线程同时预占：100 积分池、每次 15，应恰好成功 6 个，永不为负。"""
    billing_service.grant_plan_credits(billing_db, "test", Decimal("100"), 30)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(idx: int) -> None:
        try:
            billing_service.reserve(billing_db, f"resv:race:{idx}", Decimal("15"))
            with lock:
                outcomes.append("ok")
        except billing_service.InsufficientCreditsError:
            with lock:
                outcomes.append("insufficient")

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(attempt, range(10)))

    assert outcomes.count("ok") == 6
    assert outcomes.count("insufficient") == 4
    final = _account(billing_db)
    assert final["plan_available_micro"] == 10_000_000
    assert final["plan_reserved_micro"] == 90_000_000
    with db_connection() as conn:
        total_reserved = conn.execute(
            "SELECT COUNT(*) FROM credit_ledger WHERE type='usage_reserve'"
        ).fetchone()[0]
    assert total_reserved == 6


def test_settle_links_usage_event_with_price_snapshot(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    billing_service.reserve(billing_db, "resv:link", Decimal("3"))
    event = usage_repo.insert(
        billing_db, None, "lyrics.generate", "standalone", "test-model",
        1000, 500, 1500, "succeeded", None, 12.0, now(),
    )
    billed = billing_service.settle("resv:link", "test-model", 1000, 500, usage_event_id=int(event["id"]))
    assert billed == Decimal("2.500000")
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM usage_events WHERE id=?", (event["id"],)).fetchone()
    assert row["billed_credits_micro"] == 2_500_000
    assert row["price_version_id"] == 1  # 首个价格版本


def test_release_returns_everything(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    billing_service.reserve(billing_db, "resv:fail", Decimal("4"))
    billing_service.release("resv:fail", "上游 Provider 超时")
    final = _account(billing_db)
    assert final["plan_available_micro"] == 10_000_000
    assert final["plan_reserved_micro"] == 0
    assert billing_service.get_balance(billing_db)["recent_ledger"][0]["type"] == "usage_release"


def test_sweep_stale_reservations_recovers(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    billing_service.reserve(billing_db, "resv:crash", Decimal("4"))
    # 篡改 created_at 让它看起来是 20 分钟前
    with db_connection() as conn:
        conn.execute(
            "UPDATE credit_reservations SET created_at=? WHERE reference_id=?",
            ((datetime.now(UTC) - timedelta(minutes=20)).isoformat(), "resv:crash"),
        )
    assert billing_service.sweep_stale_reservations(600) == 1
    assert _account(billing_db)["plan_available_micro"] == 10_000_000


def test_expire_subscriptions_zeroes_plan_credits_once(billing_db):
    billing_service.grant_plan_credits(billing_db, "test", Decimal("8"), 30)
    with db_connection() as conn:
        conn.execute(
            "UPDATE subscriptions SET period_end=?",
            ((datetime.now(UTC) - timedelta(days=1)).isoformat(),),
        )
    assert billing_service.expire_subscriptions() == 1
    assert _account(billing_db)["plan_available_micro"] == 0
    # 再跑一遍不再重复清零（幂等）
    assert billing_service.expire_subscriptions() == 0
    ledger = billing_service.get_balance(billing_db)["recent_ledger"]
    expires = [entry for entry in ledger if entry["type"] == "expiration"]
    assert len(expires) == 1
    assert expires[0]["amount_credits"] == "-8.000000"


def test_plan_priority_plan_bucket_first(billing_db):
    """混合余额时先烧套餐，不够再动预付（方案 §2.2）。"""
    billing_service.grant_plan_credits(billing_db, "test", Decimal("1.5"), 30)
    with db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        billing_repo.ensure_account(conn, billing_db, now())
        account = billing_repo.get_account(conn, billing_db)
        assert account is not None
        billing_repo.update_account(
            conn, billing_db,
            plan_available=account["plan_available_micro"],
            plan_reserved=account["plan_reserved_micro"],
            prepaid_available=3_000_000,
            prepaid_reserved=0,
            now=now(),
        )
    billing_service.reserve(billing_db, "resv:mixed", Decimal("2"))
    account = _account(billing_db)
    assert account["plan_available_micro"] == 0
    assert account["plan_reserved_micro"] == 1_500_000
    assert account["prepaid_available_micro"] == 2_500_000
    assert account["prepaid_reserved_micro"] == 500_000


# ===== Runtime 集成：enforce 拒上游 / track 只记账 =====

@pytest.fixture
def staging_entry(monkeypatch):
    """注入一个不走真实模型的替身能力，间谍化 executor 确认调用顺序。"""
    calls: list[str] = []

    def executor(inputs):
        calls.append("executor")
        return {"content": "ok", "usage": {"model": "test-model", "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}

    from dataclasses import replace

    from services.capabilities import runtime

    stub = replace(
        runtime.CAPABILITY_REGISTRY["lyrics.generate"],
        executor=executor,
        billing_model=lambda: "test-model",
        billing_estimate=lambda: Decimal("1"),
    )
    monkeypatch.setitem(runtime.CAPABILITY_REGISTRY, "lyrics.generate", stub)
    return calls


def test_runtime_enforce_blocks_insufficient_before_executor(billing_db, staging_entry, monkeypatch):
    monkeypatch.setattr("core.config.BILLING_MODE", "enforce")
    import asyncio

    from services.capabilities import runtime

    async def exec_run():
        return await runtime.run_capability(
            "lyrics.generate",
            {"theme": "moon"},
            context=runtime.CapabilityContext(user_id=billing_db, project_id=None, source="standalone"),
        )

    # 先不充值：应被预占拦截，executor 不允许被触碰
    result = asyncio.run(exec_run())
    assert result.status == "failed"
    assert "积分不足" in (result.error or "")
    assert staging_entry == []

    # 充值后放行，executor 被调一次，结算后套餐余额正确
    billing_service.grant_plan_credits(billing_db, "test", Decimal("10"), 30)
    result = asyncio.run(exec_run())
    assert result.status == "succeeded"
    assert staging_entry == ["executor"]
    # billed = 100/1000×1.0 + 50/1000×2.0 + 0.5 每次调用 = 0.7 积分；预占 1，差额 0.3 退回，净扣 0.7
    account = _account(billing_db)
    assert account["plan_reserved_micro"] == 0
    assert account["plan_available_micro"] == 9_300_000


def test_runtime_track_mode_logs_but_never_blocks(billing_db, staging_entry, monkeypatch):
    monkeypatch.setattr("core.config.BILLING_MODE", "track")
    import asyncio

    from services.capabilities import runtime

    result = asyncio.run(
        runtime.run_capability(
            "lyrics.generate",
            {"theme": "moon"},
            context=runtime.CapabilityContext(user_id=billing_db, project_id=None, source="standalone"),
        )
    )
    assert result.status == "succeeded"
    assert staging_entry == ["executor"]
    # track 不走预占（欠费也不拦）：账本没扣，甚至账户行都没建
    balance = billing_service.get_balance(billing_db)
    assert balance["plan_credits"] == "0.000000"
    assert balance["plan_reserved_credits"] == "0.000000"
    assert balance["recent_ledger"] == []
