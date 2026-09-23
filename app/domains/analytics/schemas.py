from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class MonthlyAnalytics(BaseModel):
    month: int
    month_name: str
    orders: int
    revenue: Decimal
    material_cost: Decimal
    designer_cost: Decimal
    profit: Decimal
    inventory_units_used: int
    inventory_value_used: Decimal


class DesignerAnalytics(BaseModel):
    designer_id: UUID
    designer_name: str
    completed_tasks: int
    total_charge: Decimal


class AnalyticsSummary(BaseModel):
    year: int
    total_orders: int
    total_revenue: Decimal
    total_material_cost: Decimal
    total_designer_cost: Decimal
    total_profit: Decimal
    total_inventory_units_used: int
    total_inventory_value_used: Decimal
    monthly: list[MonthlyAnalytics]
    designers: list[DesignerAnalytics]
