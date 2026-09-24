"""计费 API 的请求/响应模型。金额对外统一以字符串 Decimal 传输，杜绝浮点。"""

from decimal import Decimal

from pydantic import BaseModel, Field


class TestGrantRequest(BaseModel):
    credits: Decimal = Field(default=Decimal("100"), gt=0, le=Decimal("100000"))
    period_days: int = Field(default=30, ge=1, le=3660)


class LedgerEntryView(BaseModel):
    type: str
    amount_credits: str
    plan_balance_after: str
    prepaid_balance_after: str
    description: str
    created_at: str


class BalanceResponse(BaseModel):
    plan_credits: str
    prepaid_credits: str
    plan_reserved_credits: str
    prepaid_reserved_credits: str
    recent_ledger: list[LedgerEntryView]


class TestGrantResponse(BaseModel):
    subscription_id: int
    credits: str
    period_end: str
