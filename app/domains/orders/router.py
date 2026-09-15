from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import (
    RequireSuperAdminOrFrontDesk,
)
from app.domains.orders.models import OrderStatus
from app.domains.orders.schemas import (
    OrderCreate,
    OrderFileResponse,
    OrderResponse,
    OrderUpdate,
)
from app.domains.orders.service import OrderService
from app.domains.users.models import User
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)

service = OrderService()


@router.post(
    "",
    response_model=OrderResponse,
)
async def create_order(
    data: OrderCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.create(
        db,
        data,
    )


@router.get(
    "",
    response_model=PaginatedResponse[OrderResponse],
)
async def get_orders(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
    pagination: Pagination,
    search: str | None = None,
    status: OrderStatus | None = None,
):
    return await service.get_all(
        db,
        pagination,
        search,
        status,
    )


@router.post(
    "/{order_id}/files",
    response_model=OrderFileResponse,
)
async def upload_order_file(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
    file: UploadFile = File(...),
):
    return await service.upload_file(
        db,
        order_id,
        file,
        current_user,
    )


@router.delete(
    "/files/{file_id}",
)
async def delete_order_file(
    file_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.delete_file(
        db,
        file_id,
        current_user,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
)
async def get_order(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_by_id(
        db,
        order_id,
    )


@router.patch(
    "/{order_id}",
    response_model=OrderResponse,
)
async def update_order(
    order_id: str,
    data: OrderUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.update(
        db,
        order_id,
        data,
    )


@router.delete(
    "/{order_id}",
)
async def delete_order(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        User,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.delete(
        db,
        order_id,
    )
