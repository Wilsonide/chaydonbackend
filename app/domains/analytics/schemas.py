from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DailyAnalytics(BaseModel):
    day: int
    date: str

    orders: int = 0
    order_value: Decimal = Decimal("0.00")
    revenue_received: Decimal = Decimal("0.00")
    outstanding_balance: Decimal = Decimal("0.00")


class MonthlyAnalytics(BaseModel):
    month: int
    month_name: str

    orders: int = 0
    order_value: Decimal = Decimal("0.00")
    revenue_received: Decimal = Decimal("0.00")
    outstanding_balance: Decimal = Decimal("0.00")

    daily: list[DailyAnalytics] = Field(default_factory=list)


class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int

    total_orders: int = 0
    total_order_value: Decimal = Decimal("0.00")
    total_revenue_received: Decimal = Decimal("0.00")
    total_outstanding_balance: Decimal = Decimal("0.00")

    monthly: list[MonthlyAnalytics] = Field(default_factory=list)