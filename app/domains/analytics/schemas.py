from decimal import Decimal

from pydantic import BaseModel


class DailyAnalytics(BaseModel):
    day: int
    date: str
    orders: int
    revenue: Decimal
    material_cost: Decimal
    profit: Decimal
    inventory_units_used: int
    inventory_value_used: Decimal


class MonthlyAnalytics(BaseModel):
    month: int
    month_name: str
    orders: int
    revenue: Decimal
    material_cost: Decimal
    profit: Decimal
    inventory_units_used: int
    inventory_value_used: Decimal
    daily: list[DailyAnalytics]


class AnalyticsSummary(BaseModel):
    year: int
    total_orders: int
    total_revenue: Decimal
    total_material_cost: Decimal
    total_profit: Decimal
    total_inventory_units_used: int
    total_inventory_value_used: Decimal
    monthly: list[MonthlyAnalytics]
