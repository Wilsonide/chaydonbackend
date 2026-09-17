from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models import (
    InventoryItem,
    MovementType,
    StockMovement,
)
from app.domains.inventory.repository import InventoryRepository
from app.domains.inventory.schemas import (
    InventoryCreate,
    InventoryUpdate,
    ManualAdjustment,
    ProductionConsumption,
    StockMovementCreate,
)
from app.shared.pagination import PaginationParams
from app.shared.responses import build_page


class InventoryService:
    def __init__(self):
        self.repo = InventoryRepository()

    async def create(
        self,
        db: AsyncSession,
        data: InventoryCreate,
    ):
        item = InventoryItem(**data.model_dump())

        return await self.repo.create(
            db,
            item,
        )

    async def get_all(
        self,
        db: AsyncSession,
        pagination: PaginationParams,
        search: str | None,
    ):
        items, total = await self.repo.get_all(
            db,
            pagination,
            search,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def update(
        self,
        db: AsyncSession,
        item_id: str,
        data: InventoryUpdate,
    ):
        item = await self.repo.get_by_id(
            db,
            item_id,
        )

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found",
            )

        for key, value in data.model_dump(
            exclude_unset=True,
        ).items():
            setattr(item, key, value)

        return await self.repo.save(
            db,
            item,
        )

    async def add_stock(
        self,
        db: AsyncSession,
        item_id: str,
        data: StockMovementCreate,
        user_id: str,
    ):
        item = await self.repo.get_by_id(
            db,
            item_id,
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found",
            )

        if data.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity must be greater than zero",
            )

        if data.movement_type == MovementType.STOCK_IN:
            item.quantity += data.quantity

        elif data.movement_type == MovementType.STOCK_OUT:
            if item.quantity < data.quantity:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient stock",
                )

            item.quantity -= data.quantity

        else:
            raise HTTPException(
                status_code=400,
                detail=("Use manual adjustment endpoint for ADJUSTMENT"),
            )

        movement = StockMovement(
            item_id=item.id,
            quantity=data.quantity,
            movement_type=data.movement_type,
            reason=data.reason,
            recorded_by=user_id,
            production_folder_id=data.production_folder_id,
        )

        return await self.repo.save_with_movement(
            db,
            item,
            movement,
        )

    async def manual_adjustment(
        self,
        db: AsyncSession,
        item_id: str,
        data: ManualAdjustment,
        user_id: str,
    ):
        item = await self.repo.get_by_id(
            db,
            item_id,
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found",
            )

        old = item.quantity

        item.quantity = data.new_quantity

        movement = StockMovement(
            item_id=item.id,
            quantity=data.new_quantity,
            movement_type=MovementType.ADJUSTMENT,
            reason=(f"{data.reason} (Old:{old} New:{data.new_quantity})"),
            recorded_by=user_id,
        )

        return await self.repo.save_with_movement(
            db,
            item,
            movement,
        )

    async def consume_for_production(
        self,
        db: AsyncSession,
        folder_id: str,
        data: ProductionConsumption,
        user_id: str,
    ):
        item = await self.repo.get_by_id(
            db,
            data.item_id,
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found",
            )

        if item.quantity < data.quantity:
            raise HTTPException(
                status_code=400,
                detail=(f"Only {item.quantity} {item.unit} available"),
            )

        item.quantity -= data.quantity

        movement = StockMovement(
            item_id=item.id,
            quantity=data.quantity,
            movement_type=MovementType.STOCK_OUT,
            reason=data.reason,
            recorded_by=user_id,
            production_folder_id=folder_id,
        )

        return await self.repo.save_with_movement(
            db,
            item,
            movement,
        )

    async def get_movements(
        self,
        db: AsyncSession,
        item_id: str,
        pagination: PaginationParams,
    ):
        item = await self.repo.get_by_id(
            db,
            item_id,
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found",
            )

        movements, total = await self.repo.get_movements(
            db,
            item_id,
            pagination,
        )

        return build_page(
            items=movements,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def low_stock(
        self,
        db: AsyncSession,
    ):
        return await self.repo.get_low_stock(db)

    async def dashboard(
        self,
        db: AsyncSession,
    ):
        return await self.repo.dashboard_summary(db)
