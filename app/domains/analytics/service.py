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
            db=db,
            year=year,
        )

        return AnalyticsSummary(
            year=year,
            total_orders=analytics["total_orders"],
            total_order_value=analytics["total_order_value"],
            total_revenue_received=analytics[
                "total_revenue_received"
            ],
            total_outstanding_balance=analytics[
                "total_outstanding_balance"
            ],
            monthly=analytics["monthly"],
        )