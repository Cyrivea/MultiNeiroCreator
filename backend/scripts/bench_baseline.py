"""压测基线（H3）：给简历留可复现的数字，不含任何修饰。

两条链分开测，避免把“上游模型延迟”误当“框架容量”：

1. **infra 链**（框架轻接口）：GET /history、/workflows/draft、/documents，
   并发梯度打满框架/数据库，测 P95、QPS、错误率——这部分数字归我们框架。
2. **chat 链**（真实 LLM）：顺序请求 /chat（无法并发，上游就是慢），记录 TTFT 与
   整体耗时分布。这数字归“我们与上游的协同”，不拿它冒充框架数字。

运行（backend/ 下，需要本地服务跑着）：
    uv run python scripts/bench_baseline.py --users 8 --infra-concurrency 5 20 50

产出 `bench_result.json` + 控制台摘要。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
RESULT_FILE = Path(__file__).resolve().parents[1] / "bench_result.json"


async def make_users(count: int) -> list[str]:
    """创建/登录 bench 用户群，返回 token 列表（压并发用，分担每用户限流配额）。"""
    import sqlite3

    from core.database import db_connection
    from services.auth_service import create_token, hash_password

    tokens = []
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        for i in range(count):
            username = f"bench-{i}@local.test"
            row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if row is None:
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, profile, created_at) VALUES (?,?,?,?)",
                    (username, hash_password("Bench#2026"), "", "2026-01-01"),
                )
                uid = cur.lastrowid
            else:
                uid = row["id"]
            tokens.append(create_token(uid, username))
    return tokens


def pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, int(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


async def measure(
    client: httpx.AsyncClient, tokens: list[str], concurrency: int, per_request: int
) -> dict:
    """infra 链单档：concurrency 并发 × per_request 总请求数。"""
    latencies: list[float] = []
    statuses: dict[int, int] = {}
    errors = 0
    sem = asyncio.Semaphore(concurrency)

    async def one(i: int) -> None:
        nonlocal errors
        token = tokens[i % len(tokens)]
        url = (
            f"{BASE}/history" if i % 3 == 0 else
            f"{BASE}/workflows/draft" if i % 3 == 1 else
            f"{BASE}/documents"
        )
        async with sem:
            started = time.perf_counter()
            try:
                r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                statuses[r.status_code] = statuses.get(r.status_code, 0) + 1
                if r.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1
            latencies.append((time.perf_counter() - started) * 1000)

    await asyncio.gather(*(one(i) for i in range(per_request)))
    latencies.sort()
    return {
        "concurrency": concurrency,
        "total": per_request,
        "errors": errors,
        "ok_rate": round(1.0 - errors / max(1, per_request), 4),
        "p50_ms": round(pct(latencies, 0.5), 1),
        "p95_ms": round(pct(latencies, 0.95), 1),
        "p99_ms": round(pct(latencies, 0.99), 1),
        "throughput_rps_proxy": round(per_request / (max(latencies) / 1000 if latencies else 1), 1),
    }


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--users", type=int, default=8)
    p.add_argument("--infra-concurrency", type=int, nargs="+", default=[5, 20, 50])
    p.add_argument("--infra-total", type=int, default=100, help="每档总请求数")
    p.add_argument("--chat-rounds", type=int, default=5, help="chat 链顺序请求次数")
    args = p.parse_args()

    tokens = await make_users(args.users)
    infra_rows = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for conc in args.infra_concurrency:
            row = await measure(client, tokens, conc, args.infra_total)
            infra_rows.append(row)
            print(
                f"[infra] conc={conc:>3} | total={row['total']} errors={row['errors']} "
                f"p50={row['p50_ms']}ms p95={row['p95_ms']}ms"
            )

    # ---- chat 链：顺序请求，测真实 LLM 首字与总耗时 ----
    chat_lat: list[float] = []
    chat_ttft: list[float] = []
    chat_errors = 0
    async with httpx.AsyncClient(timeout=90.0) as client:
        token = tokens[0]
        for i in range(args.chat_rounds):
            started = time.perf_counter()
            first_at: float | None = None
            try:
                r = await client.post(
                    f"{BASE}/chat",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"message": f"压测问候 {i}", "project_id": None},
                )
                ttft_done = False
                async for line in r.aiter_lines():
                    if not ttft_done and line.startswith("data:") and '"content"' in line:
                        first_at = time.perf_counter()
                        ttft_done = True
                if r.status_code != 200:
                    chat_errors += 1
            except Exception as exc:
                chat_errors += 1
                print(f"[chat] round {i} error: {type(exc).__name__}")
                continue
            chat_lat.append((time.perf_counter() - started) * 1000)
            if first_at:
                chat_ttft.append((first_at - started) * 1000)
            print(
                f"[chat] {i+1}/{args.chat_rounds} total={chat_lat[-1]:.0f}ms "
                f"ttft={(chat_ttft[-1] if chat_ttft else 0):.0f}ms"
            )
            await asyncio.sleep(6.2)  # 尊重每用户每分钟 10 次的聊天限流

    chat_lat.sort()
    chat_ttft.sort()
    chat_summary = {
        "rounds": args.chat_rounds,
        "errors": chat_errors,
        "total_p50_ms": round(pct(chat_lat, 0.5), 1) if chat_lat else None,
        "total_p95_ms": round(pct(chat_lat, 0.95), 1) if chat_lat else None,
        "ttft_p50_ms": round(pct(chat_ttft, 0.5), 1) if chat_ttft else None,
        "ttft_p95_ms": round(pct(chat_ttft, 0.95), 1) if chat_ttft else None,
    }

    out = {
        "meta": {"note": "infra=框架轻接口并发链; chat=真实 LLM 顺序链（上游智谱）"},
        "infra": infra_rows,
        "chat": chat_summary,
    }
    RESULT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {RESULT_FILE.name}")
    print(json.dumps(chat_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
