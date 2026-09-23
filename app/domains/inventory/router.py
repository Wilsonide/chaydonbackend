from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import (
    RequireSuperAdmin,
    RequireSuperAdminOrFrontDesk,
)
from app.domains.inventory.schemas import (
    InventoryCreate,
    InventoryDashboardResponse,
    InventoryResponse,
    InventoryUpdate,
    LowStockResponse,
    ManualAdjustment,
    OrderMaterialCalculationResponse,
    OrderMaterialRequirementCreate,
    OrderMaterialRequirementResponse,
    ProductionConsumption,
    StockMovementCreate,
    StockMovementResponse,
)
from app.domains.inventory.service import InventoryService
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"],
)

service = InventoryService()


# ============================================================
# INVENTORY ITEMS
# ============================================================


@router.post(
    "",
    response_model=InventoryResponse,
)
async def create_item(
    data: InventoryCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.create(
        db,
        data,
    )


@router.get(
    "",
    response_model=PaginatedResponse[InventoryResponse],
)
async def get_items(
    pagination: Pagination,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
    search: Annotated[
        str | None,
        Query(),
    ] = None,
):
    return await service.get_all(
        db,
        pagination,
        search,
    )


@router.patch(
    "/{item_id}",
    response_model=InventoryResponse,
)
async def update_item(
    item_id: str,
    data: InventoryUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.update(
        db,
        item_id,
        data,
    )


# ============================================================
# STOCK MOVEMENTS
# ============================================================


@router.post(
    "/{item_id}/movement",
    response_model=StockMovementResponse,
)
async def add_stock_movement(
    item_id: str,
    data: StockMovementCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.add_stock(
        db,
        item_id,
        data,
        str(current_user.id),
    )


@router.post(
    "/{item_id}/adjust",
    response_model=StockMovementResponse,
)
async def manual_adjustment(
    item_id: str,
    data: ManualAdjustment,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.manual_adjustment(
        db,
        item_id,
        data,
        str(current_user.id),
    )


# ============================================================
# PRINT ORDER MATERIAL REQUIREMENTS
# ============================================================


@router.post(
    "/orders/{order_id}/materials",
    response_model=OrderMaterialRequirementResponse,
)
async def add_order_material(
    order_id: str,
    data: OrderMaterialRequirementCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.add_order_material_requirement(
        db,
        order_id,
        data,
    )


@router.get(
    "/orders/{order_id}/materials",
    response_model=OrderMaterialCalculationResponse,
)
async def calculate_order_materials(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.calculate_order_materials(
        db,
        order_id,
    )


@router.post(
    "/orders/{order_id}/materials/consume",
    response_model=list[StockMovementResponse],
)
async def consume_order_materials(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.consume_order_materials(
        db,
        order_id,
        str(current_user.id),
    )


# ============================================================
# PRINT ORDER INVENTORY HISTORY
# ============================================================


@router.get(
    "/orders/{order_id}/movements",
    response_model=PaginatedResponse[StockMovementResponse],
)
async def order_movement_history(
    order_id: str,
    pagination: Pagination,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_order_movements(
        db,
        order_id,
        pagination,
    )


# ============================================================
# PRODUCTION CONSUMPTION
# ============================================================


@router.post(
    "/production/{folder_id}/consume",
    response_model=StockMovementResponse,
)
async def consume_for_production(
    folder_id: str,
    data: ProductionConsumption,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.consume_for_production(
        db,
        folder_id,
        data,
        str(current_user.id),
    )


# ============================================================
# ITEM MOVEMENT HISTORY
# ============================================================


@router.get(
    "/{item_id}/movements",
    response_model=PaginatedResponse[StockMovementResponse],
)
async def movement_history(
    item_id: str,
    pagination: Pagination,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_movements(
        db,
        item_id,
        pagination,
    )


# ============================================================
# LOW STOCK
# ============================================================


@router.get(
    "/alerts/low-stock",
    response_model=list[LowStockResponse],
)
async def low_stock(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.low_stock(db)


# ============================================================
# DASHBOARD
# ============================================================


@router.get(
    "/dashboard/summary",
    response_model=InventoryDashboardResponse,
)
async def dashboard_summary(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.dashboard(db)
