from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.inventory.models import (
    InventoryItem,
    MovementType,
    OrderMaterialRequirement,
    StockMovement,
)
from app.domains.inventory.repository import InventoryRepository
from app.domains.inventory.schemas import (
    InventoryCreate,
    InventoryUpdate,
    ManualAdjustment,
    OrderMaterialRequirementCreate,
    ProductionConsumption,
    StockMovementCreate,
)
from app.domains.orders.models import Order
from app.shared.pagination import PaginationParams
from app.shared.responses import build_page


class InventoryService:
    def __init__(self):
        self.repo = InventoryRepository()

    # ============================================================
    # INVENTORY ITEMS
    # ============================================================

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

    # ============================================================
    # STOCK MOVEMENTS
    # ============================================================

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

        movement_price = float(item.unit_selling_price)

        if data.movement_type == MovementType.STOCK_IN:
            item.quantity += data.quantity

            if data.unit_selling_price is not None:
                if data.unit_selling_price < 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Unit selling price cannot be negative",
                    )

                item.unit_selling_price = data.unit_selling_price

            movement_price = float(item.unit_selling_price)

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
                detail="Use manual adjustment endpoint for ADJUSTMENT",
            )

        movement = StockMovement(
            item_id=item.id,
            quantity=data.quantity,
            movement_type=data.movement_type,
            unit_selling_price=movement_price,
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
            unit_selling_price=item.unit_selling_price,
            reason=(f"{data.reason} (Old:{old} New:{data.new_quantity})"),
            recorded_by=user_id,
        )

        return await self.repo.save_with_movement(
            db,
            item,
            movement,
        )

    # ============================================================
    # PRODUCTION FOLDER CONSUMPTION
    # ============================================================

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

        if data.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity must be greater than zero",
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
            unit_selling_price=item.unit_selling_price,
            reason=data.reason,
            recorded_by=user_id,
            production_folder_id=folder_id,
        )

        return await self.repo.save_with_movement(
            db,
            item,
            movement,
        )

    # ============================================================
    # ITEM MOVEMENT HISTORY
    # ============================================================

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

    # ============================================================
    # LOW STOCK
    # ============================================================

    async def low_stock(
        self,
        db: AsyncSession,
    ):
        return await self.repo.get_low_stock(db)

    # ============================================================
    # DASHBOARD
    # ============================================================

    async def dashboard(
        self,
        db: AsyncSession,
    ):
        return await self.repo.dashboard_summary(db)

    # ============================================================
    # ORDER MATERIAL REQUIREMENTS
    #
    # PRINT orders:
    #     Order -> Print Queue
    #
    # DESIGN orders:
    #     Order -> ProductionFolder -> Task
    #            -> COMPLETED -> Print Queue
    #
    # Once an order reaches the Print Queue, both order types
    # use the same material workflow.
    # ============================================================

    async def calculate_order_materials(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        order = await db.get(
            Order,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        requirements = await self.repo.get_order_material_requirements(
            db,
            order_id,
        )

        total_required_cost = 0
        total_consumed_cost = 0
        total_remaining_cost = 0

        for requirement in requirements:
            unit_price = float(requirement.unit_selling_price)

            total_required_cost += requirement.required_quantity * unit_price

            total_consumed_cost += requirement.consumed_quantity * unit_price

            total_remaining_cost += requirement.remaining_quantity * unit_price

        return {
            "order_id": order.id,
            "total_required_cost": total_required_cost,
            "total_consumed_cost": total_consumed_cost,
            "total_remaining_cost": total_remaining_cost,
            "requirements": requirements,
        }

    async def add_order_material_requirement(
        self,
        db: AsyncSession,
        order_id: str,
        data: OrderMaterialRequirementCreate,
    ):
        order = await db.get(
            Order,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        if data.required_quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Required quantity must be greater than zero",
            )

        item = await self.repo.get_by_id(
            db,
            str(data.inventory_item_id),
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found",
            )

        requirement = OrderMaterialRequirement(
            order_id=order.id,
            inventory_item_id=item.id,
            required_quantity=data.required_quantity,
            consumed_quantity=0,
            unit_selling_price=item.unit_selling_price,
        )

        try:
            await self.repo.create_material_requirement(
                db,
                requirement,
            )

            await db.commit()
            await db.refresh(requirement)

        except Exception:
            await db.rollback()
            raise

        return requirement

    # ============================================================
    # CONSUME ALL REMAINING ORDER MATERIALS
    #
    # This is used by the Print Queue.
    #
    # Important:
    # We lock every required inventory item first and verify
    # ALL stock levels before deducting anything.
    #
    # Therefore, if one material is unavailable, nothing is
    # consumed.
    # ============================================================

    async def consume_order_materials(
        self,
        db: AsyncSession,
        order_id: str,
        user_id: str,
    ):
        """
        Consume all remaining material requirements for an order.

        Works for both:
            - PRINT orders
            - DESIGN orders that have completed their design workflow

        All inventory items are locked before deduction so that
        concurrent consumption cannot oversell stock.

        The stock movement reason is stored as:

            Material consumed for order [order title] by [customer name]
        """
        # --------------------------------------------------------
        # GET ORDER WITH CUSTOMER
        # --------------------------------------------------------

        result = await db.execute(
            select(Order)
            .options(selectinload(Order.customer))
            .where(Order.id == order_id)
        )

        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # --------------------------------------------------------
        # GET MATERIAL REQUIREMENTS
        # --------------------------------------------------------

        requirements = await self.repo.get_order_material_requirements(
            db,
            order_id,
        )

        if not requirements:
            raise HTTPException(
                status_code=400,
                detail="No material requirements found for this order",
            )

        # --------------------------------------------------------
        # FIND REQUIREMENTS STILL NEEDING CONSUMPTION
        # --------------------------------------------------------

        pending_requirements = [
            requirement
            for requirement in requirements
            if requirement.remaining_quantity > 0
        ]

        if not pending_requirements:
            raise HTTPException(
                status_code=400,
                detail="All required materials have already been consumed",
            )

        # --------------------------------------------------------
        # LOCK INVENTORY ITEMS
        #
        # Sort by inventory ID first so concurrent transactions
        # acquire locks in a consistent order.
        # --------------------------------------------------------

        pending_requirements.sort(
            key=lambda requirement: str(requirement.inventory_item_id)
        )

        locked_items = {}

        try:
            for requirement in pending_requirements:
                item_id = str(requirement.inventory_item_id)

                if item_id not in locked_items:
                    item = await self.repo.get_by_id_for_update(
                        db,
                        item_id,
                    )

                    if not item:
                        raise HTTPException(
                            status_code=404,
                            detail=(f"Inventory item {item_id} not found"),
                        )

                    locked_items[item_id] = item

            # ----------------------------------------------------
            # CHECK ALL STOCK BEFORE MAKING ANY DEDUCTIONS
            # ----------------------------------------------------

            for requirement in pending_requirements:
                item = locked_items[str(requirement.inventory_item_id)]

                required_quantity = requirement.remaining_quantity

                if item.quantity < required_quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Insufficient stock for "
                            f"'{item.name}'. "
                            f"Required: {required_quantity}, "
                            f"Available: {item.quantity}"
                        ),
                    )

            # ----------------------------------------------------
            # BUILD MOVEMENT REASON
            # ----------------------------------------------------

            customer_name = order.customer.name

            movement_reason = (
                f"Material consumed for order {order.title} by {customer_name}"
            )

            movements = []

            # ----------------------------------------------------
            # DEDUCT STOCK
            # ----------------------------------------------------

            for requirement in pending_requirements:
                item = locked_items[str(requirement.inventory_item_id)]

                consumed_quantity = requirement.remaining_quantity

                # Deduct inventory
                item.quantity -= consumed_quantity

                # Update requirement
                requirement.consumed_quantity += consumed_quantity

                # Create movement
                movement = StockMovement(
                    item_id=item.id,
                    quantity=consumed_quantity,
                    movement_type=MovementType.STOCK_OUT,
                    unit_selling_price=item.unit_selling_price,
                    reason=movement_reason,
                    recorded_by=user_id,
                    order_id=order.id,
                )

                db.add(item)
                db.add(requirement)
                db.add(movement)

                movements.append(movement)

            # ----------------------------------------------------
            # COMMIT EVERYTHING TOGETHER
            # ----------------------------------------------------

            await db.commit()

            # ----------------------------------------------------
            # REFRESH MOVEMENTS
            # ----------------------------------------------------

            for movement in movements:
                await db.refresh(movement)

            return movements

        except Exception:
            await db.rollback()
            raise

    # ============================================================
    # ORDER INVENTORY HISTORY
    # ============================================================

    async def get_order_movements(
        self,
        db: AsyncSession,
        order_id: str,
        pagination: PaginationParams,
    ):
        order = await db.get(
            Order,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        movements, total = await self.repo.get_order_movements(
            db,
            order_id,
            pagination,
        )

        return build_page(
            items=movements,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )
