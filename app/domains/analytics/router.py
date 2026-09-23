from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.analytics.schemas import AnalyticsSummary
from app.domains.analytics.service import AnalyticsService
from app.domains.auth.permissions import RequireSuperAdmin

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)

service = AnalyticsService()


@router.get(
    "/yearly",
    response_model=AnalyticsSummary,
)
async def get_yearly_analytics(
    year: Annotated[
        int,
        Query(
            ge=2020,
            le=2100,
            description="Analytics year",
        ),
    ],
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    return await service.get_yearly_analytics(
        db,
        year,
    )
