"""core/ratelimit.py 的单元测试 + 并发压测。

使用本地 Redis 的 db 15 作为专用测试库（每个用例前后 FLUSHDB），
本地 Redis 未启动时整组跳过。运行方式（backend 目录下）：
    .venv/bin/python -m pytest tests/ -v
"""
import asyncio
import time

import pytest
import redis.asyncio as aioredis

from core import ratelimit

TEST_REDIS_URL = "redis://localhost:6379/15"


@pytest.fixture
async def rl(monkeypatch):
    client = aioredis.Redis(
        connection_pool=aioredis.BlockingConnectionPool.from_url(
            TEST_REDIS_URL, max_connections=50, timeout=5, decode_responses=True
        )
    )
    try:
        await client.ping()
    except Exception:
        pytest.skip("本地 Redis 未启动，跳过限流测试")
    await client.flushdb()
    monkeypatch.setattr(ratelimit, "redis_client", client)
    yield ratelimit
    await client.flushdb()
    await client.aclose()


async def test_hit_within_limit(rl):
    for _ in range(5):
        assert await rl.hit("t_min", "u1", 5, 60) is None
    wait = await rl.hit("t_min", "u1", 5, 60)
    assert wait is not None and 1 <= wait <= 60


async def test_hit_isolated_keys(rl):
    assert await rl.hit("t_min", "u1", 1, 60) is None
    assert await rl.hit("t_min", "u1", 1, 60) is not None
    assert await rl.hit("t_min", "u2", 1, 60) is None


async def test_window_expiry(rl):
    assert await rl.hit("t_cd", "u1", 1, 1) is None
    assert await rl.hit("t_cd", "u1", 1, 1) is not None
    await asyncio.sleep(1.2)
    assert await rl.hit("t_cd", "u1", 1, 1) is None


async def test_quota_check_then_add(rl):
    limit = 100
    assert await rl.consume_quota("t_up", "u1", 60, limit, 3600) is True
    assert await rl.consume_quota("t_up", "u1", 50, limit, 3600) is False
    assert await rl.consume_quota("t_up", "u1", 40, limit, 3600) is True


def test_seconds_until_midnight_range():
    s = ratelimit._seconds_until_midnight()
    assert 1 <= s <= 86400


async def test_concurrent_accuracy_and_perf(rl):
    limit, total = 500, 1000
    start = time.perf_counter()
    results = await asyncio.gather(*(rl.hit("t_conc", "u1", limit, 60) for _ in range(total)))
    elapsed = time.perf_counter() - start
    allowed = sum(1 for r in results if r is None)
    assert allowed == limit
    per_op_ms = elapsed / total * 1000
    print(f"\n并发压测：{total} 次 hit 共 {elapsed:.3f}s，单次约 {per_op_ms:.3f}ms")
    assert per_op_ms < 50
