"""计费账本 SQL 层：只收连接句柄，事务边界由 services/billing_service 控制。

为什么与其它 repo 的风格（库里自开连接）不同：
预占 / 结算必须「读账户 → 改账户 → 写预占行 → 写流水」在同一个 BEGIN IMMEDIATE
事务里完成，拆成四次自开连接等于把竞态门重新打开。所以本层的所有函数都要求
调用方传入 conn，由 service 负责 BEGIN/COMMIT/ROLLBACK。
"""

from __future__ import annotations

import sqlite3
from typing import Any


def ensure_account(conn: sqlite3.Connection, user_id: int, now: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO credit_accounts (user_id, updated_at) VALUES (?, ?)",
        (user_id, now),
    )


def get_account(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM credit_accounts WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def update_account(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    plan_available: int,
    plan_reserved: int,
    prepaid_available: int,
    prepaid_reserved: int,
    now: str,
) -> None:
    conn.execute(
        """
        UPDATE credit_accounts SET
            plan_available_micro=?, plan_reserved_micro=?,
            prepaid_available_micro=?, prepaid_reserved_micro=?,
            updated_at=?
        WHERE user_id=?
        """,
        (plan_available, plan_reserved, prepaid_available, prepaid_reserved, now, user_id),
    )


def insert_subscription(
    conn: sqlite3.Connection,
    user_id: int,
    plan: str,
    status: str,
    period_start: str,
    period_end: str,
    included_credits_micro: int,
    now: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO subscriptions
            (user_id, plan, status, period_start, period_end, included_credits_micro, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, plan, status, period_start, period_end, included_credits_micro, now, now),
    )
    assert cursor.lastrowid is not None  # INSERT 刚成功，必定有 rowid
    return cursor.lastrowid


def list_subscriptions(conn: sqlite3.Connection, user_id: int | None = None) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    if user_id is None:
        rows = conn.execute("SELECT * FROM subscriptions ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def mark_subscription_status(conn: sqlite3.Connection, subscription_id: int, status: str, now: str) -> None:
    conn.execute(
        "UPDATE subscriptions SET status=?, updated_at=? WHERE id=?",
        (status, now, subscription_id),
    )


def insert_price_version(
    conn: sqlite3.Connection,
    model_id: str,
    input_price_per_1k: str,
    output_price_per_1k: str,
    *,
    cache_price_per_1k: str = "0",
    reasoning_price_per_1k: str = "0",
    per_call_credits: str = "0",
    credit_multiplier: str = "1",
    effective_from: str,
    created_at: str,
    effective_to: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO model_price_versions
            (model_id, input_price_per_1k, output_price_per_1k, cache_price_per_1k,
             reasoning_price_per_1k, per_call_credits, credit_multiplier,
             effective_from, effective_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_id,
            input_price_per_1k,
            output_price_per_1k,
            cache_price_per_1k,
            reasoning_price_per_1k,
            per_call_credits,
            credit_multiplier,
            effective_from,
            effective_to,
            created_at,
        ),
    )
    assert cursor.lastrowid is not None  # INSERT 刚成功，必定有 rowid
    return cursor.lastrowid


def current_price_version(
    conn: sqlite3.Connection, model_id: str, now: str
) -> dict[str, Any] | None:
    """调用时点生效的价格版本：effective_from<=now 且未过期，取最近一个生效的。"""
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT * FROM model_price_versions
        WHERE model_id=? AND effective_from<=? AND (effective_to IS NULL OR effective_to>?)
        ORDER BY effective_from DESC, id DESC
        LIMIT 1
        """,
        (model_id, now, now),
    ).fetchone()
    return dict(row) if row else None


def insert_reservation(
    conn: sqlite3.Connection,
    user_id: int,
    reference_id: str,
    plan_micro: int,
    prepaid_micro: int,
    now: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO credit_reservations (user_id, reference_id, plan_micro, prepaid_micro, status, created_at)
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (user_id, reference_id, plan_micro, prepaid_micro, now),
    )
    assert cursor.lastrowid is not None  # INSERT 刚成功，必定有 rowid
    return cursor.lastrowid


def get_reservation_by_reference(
    conn: sqlite3.Connection, reference_id: str
) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM credit_reservations WHERE reference_id=?", (reference_id,)
    ).fetchone()
    return dict(row) if row else None


def close_reservation(
    conn: sqlite3.Connection, reservation_id: int, status: str, now: str
) -> None:
    conn.execute(
        "UPDATE credit_reservations SET status=?, closed_at=? WHERE id=?",
        (status, now, reservation_id),
    )


def list_stale_open_reservations(
    conn: sqlite3.Connection, older_than: str
) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM credit_reservations WHERE status='open' AND created_at < ?",
        (older_than,),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_ledger(
    conn: sqlite3.Connection,
    user_id: int,
    amount_micro: int,
    plan_balance_after_micro: int,
    prepaid_balance_after_micro: int,
    entry_type: str,
    reference_id: str,
    description: str,
    now: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO credit_ledger
            (user_id, amount_micro, plan_balance_after_micro, prepaid_balance_after_micro,
             type, reference_id, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            amount_micro,
            plan_balance_after_micro,
            prepaid_balance_after_micro,
            entry_type,
            reference_id,
            description,
            now,
        ),
    )
    assert cursor.lastrowid is not None  # INSERT 刚成功，必定有 rowid
    return cursor.lastrowid


def ledger_entry_exists(conn: sqlite3.Connection, entry_type: str, reference_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM credit_ledger WHERE type=? AND reference_id=?", (entry_type, reference_id)
    ).fetchone()
    return row is not None


def list_ledger_for_user(conn: sqlite3.Connection, user_id: int, limit: int) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, max(1, min(limit, 500))),
    ).fetchall()
    return [dict(row) for row in rows]


def link_usage_event_billing(
    conn: sqlite3.Connection,
    usage_event_id: int,
    price_version_id: int,
    billed_credits_micro: int,
) -> None:
    conn.execute(
        "UPDATE usage_events SET price_version_id=?, billed_credits_micro=? WHERE id=?",
        (price_version_id, billed_credits_micro, usage_event_id),
    )
