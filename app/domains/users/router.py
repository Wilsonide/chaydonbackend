from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.users.repository import UserRepository
from app.domains.users.schemas import DesignerResponse

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

user_repo = UserRepository()
current_user_dependency = Depends(get_current_user)


@router.get(
    "/designers",
    response_model=list[DesignerResponse],
)
async def get_graphic_designers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _=current_user_dependency,
):
    return await user_repo.get_graphic_designers(db)
