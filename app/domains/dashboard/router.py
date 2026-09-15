from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.dashboard.service import DashboardService
from app.domains.users.models import User

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

service = DashboardService()


@router.get("/summary")
async def dashboard_summary(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
):
    return await service.get_summary(
        db,
        current_user,
    )
