from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.analytics.repository import AnalyticsRepository
from app.domains.analytics.schemas import AnalyticsSummary


class AnalyticsService:
    def __init__(self):
        self.repo = AnalyticsRepository()

    async def get_yearly_analytics(
        self,
        db: AsyncSession,
        year: int,
    ) -> AnalyticsSummary:
        analytics = await self.repo.get_yearly_analytics(
            db,
            year,
        )

        monthly = analytics["monthly"]
        designers = analytics["designers"]

        # =========================================================
        # Overall totals
        # =========================================================

        total_orders = sum(month["orders"] for month in monthly)

        total_revenue = sum(
            (month["revenue"] for month in monthly),
            Decimal("0.00"),
        )

        total_material_cost = sum(
            (month["material_cost"] for month in monthly),
            Decimal("0.00"),
        )

        total_designer_cost = sum(
            (month["designer_cost"] for month in monthly),
            Decimal("0.00"),
        )

        total_profit = total_revenue - total_material_cost - total_designer_cost

        total_inventory_units_used = sum(
            month["inventory_units_used"] for month in monthly
        )

        total_inventory_value_used = sum(
            (month["inventory_value_used"] for month in monthly),
            Decimal("0.00"),
        )

        # =========================================================
        # Response
        # =========================================================

        return AnalyticsSummary(
            year=year,
            total_orders=total_orders,
            total_revenue=total_revenue,
            total_material_cost=total_material_cost,
            total_designer_cost=total_designer_cost,
            total_profit=total_profit,
            total_inventory_units_used=(total_inventory_units_used),
            total_inventory_value_used=(total_inventory_value_used),
            monthly=monthly,
            designers=designers,
        )
