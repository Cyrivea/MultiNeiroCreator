"""计费 API：余额查询与管理员测试放款（真实支付渠道后置）。

限额安全：``/billing/test-grant`` 默认关闭，只在管理员设了
``BILLING_TEST_GRANTS_ENABLED=on`` 的环境才可用——这意图是阶段 1 的
模拟账本，不是暴露给真实用户的白嫖接口。
"""

import asyncio
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from core import config
from core.deps import verify_token
from schemas.billing import (
    BalanceResponse,
    TestGrantRequest,
    TestGrantResponse,
    TestTopUpRequest,
    TestTopUpResponse,
)
from services import billing_service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user=Depends(verify_token)):
    """当前用户的积分视图：套餐/预付的可用与预占四元组 + 最近 20 条流水。"""
    return await asyncio.to_thread(billing_service.get_balance, user["id"])


@router.post("/test-grant", response_model=TestGrantResponse)
async def test_grant(req: TestGrantRequest, user=Depends(verify_token)):
    """向当前用户发放一个测试套餐（模拟账本阶段的管理员工具）。"""
    if not config.BILLING_TEST_GRANTS_ENABLED:
        raise HTTPException(status_code=403, detail="测试放款未启用（BILLING_TEST_GRANTS_ENABLED=off）")
    credits = req.credits if req.credits else Decimal(config.BILLING_TEST_GRANT_CREDITS)
    return await asyncio.to_thread(
        billing_service.grant_plan_credits,
        user["id"],
        "test",
        credits,
        req.period_days or config.BILLING_TEST_GRANT_PERIOD_DAYS,
    )


@router.post("/test-topup", response_model=TestTopUpResponse)
async def test_topup(req: TestTopUpRequest, user=Depends(verify_token)):
    """向当前用户预付余额充值（模拟订单，真实支付回调后置）。"""
    if not config.BILLING_TEST_GRANTS_ENABLED:
        raise HTTPException(status_code=403, detail="测试放款未启用（BILLING_TEST_GRANTS_ENABLED=off）")
    reference = req.order_reference or f"order:test:{uuid.uuid4().hex}"
    result = await asyncio.to_thread(
        billing_service.top_up_prepaid, user["id"], req.credits, reference
    )
    return {**result, "order_reference": reference}
