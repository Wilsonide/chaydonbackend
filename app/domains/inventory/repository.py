from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.inventory.models import (
    InventoryItem,
    OrderMaterialRequirement,
    StockMovement,
)
from app.shared.pagination import PaginationParams
from app.shared.search import ilike_search


class InventoryRepository:
    # ============================================================
    # INVENTORY ITEMS
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        item: InventoryItem,
    ):
        db.add(item)
        await db.commit()
        await db.refresh(item)

        return item

    async def get_by_id(
        self,
        db: AsyncSession,
        item_id: str,
    ):
        result = await db.execute(
            select(InventoryItem).where(InventoryItem.id == item_id)
        )

        return result.scalar_one_or_none()

    async def get_by_id_for_update(
        self,
        db: AsyncSession,
        item_id: str,
    ):
        result = await db.execute(
            select(InventoryItem).where(InventoryItem.id == item_id).with_for_update()
        )

        return result.scalar_one_or_none()

    async def save(
        self,
        db: AsyncSession,
        item: InventoryItem,
    ):
        await db.commit()
        await db.refresh(item)

        return item

    async def get_all(
        self,
        db: AsyncSession,
        pagination: PaginationParams,
        search: str | None = None,
    ):
        query = select(InventoryItem)

        search_filter = ilike_search(
            search,
            InventoryItem.name,
            InventoryItem.category,
        )

        if search_filter is not None:
            query = query.where(search_filter)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.order_by(InventoryItem.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )

        return (
            list(result.scalars().all()),
            total or 0,
        )

    # ============================================================
    # STOCK MOVEMENTS
    # ============================================================

    async def add_movement(
        self,
        db: AsyncSession,
        movement: StockMovement,
    ):
        db.add(movement)

        await db.commit()
        await db.refresh(movement)

        return movement

    async def get_movements(
        self,
        db: AsyncSession,
        item_id: str,
        pagination: PaginationParams,
    ):
        query = select(StockMovement).where(StockMovement.item_id == item_id)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.order_by(StockMovement.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )

        return (
            list(result.scalars().all()),
            total or 0,
        )

    async def save_with_movement(
        self,
        db: AsyncSession,
        item: InventoryItem,
        movement: StockMovement,
    ):
        """
        Save an inventory quantity change and its
        corresponding stock movement in one transaction.
        """

        db.add(item)
        db.add(movement)

        await db.commit()

        await db.refresh(item)
        await db.refresh(movement)

        return movement

    # ============================================================
    # LOW STOCK
    # ============================================================

    async def get_low_stock(
        self,
        db: AsyncSession,
    ):
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.quantity <= InventoryItem.minimum_quantity
            )
        )

        return list(result.scalars().all())

    # ============================================================
    # ORDER MATERIAL REQUIREMENTS
    # ============================================================

    async def get_material_requirement(
        self,
        db: AsyncSession,
        requirement_id: str,
    ):
        result = await db.execute(
            select(OrderMaterialRequirement)
            .options(selectinload(OrderMaterialRequirement.inventory_item))
            .where(OrderMaterialRequirement.id == requirement_id)
        )

        return result.scalar_one_or_none()

    async def get_order_material_requirements(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        result = await db.execute(
            select(OrderMaterialRequirement)
            .options(selectinload(OrderMaterialRequirement.inventory_item))
            .where(OrderMaterialRequirement.order_id == order_id)
            .order_by(OrderMaterialRequirement.created_at.asc())
        )

        return list(result.scalars().all())

    async def create_material_requirement(
        self,
        db: AsyncSession,
        requirement: OrderMaterialRequirement,
    ):
        """
        Add a material requirement to the current transaction.

        This method intentionally does NOT commit.
        The service controls the transaction boundary.
        """

        db.add(requirement)

        await db.flush()

        return requirement

    async def delete_material_requirement(
        self,
        db: AsyncSession,
        requirement: OrderMaterialRequirement,
    ):
        await db.delete(requirement)

        await db.flush()

    # ============================================================
    # ORDER INVENTORY MOVEMENTS
    # ============================================================

    async def get_order_movements(
        self,
        db: AsyncSession,
        order_id: str,
        pagination: PaginationParams,
    ):
        query = select(StockMovement).where(StockMovement.order_id == order_id)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.order_by(StockMovement.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )

        return (
            list(result.scalars().all()),
            total or 0,
        )

    # ============================================================
    # DASHBOARD
    # ============================================================

    async def dashboard_summary(
        self,
        db: AsyncSession,
    ):
        result = await db.execute(
            select(
                func.count(InventoryItem.id).label("total_items"),
                func.coalesce(
                    func.sum(InventoryItem.quantity),
                    0,
                ).label("total_stock_units"),
                func.coalesce(
                    func.sum(InventoryItem.quantity * InventoryItem.unit_selling_price),
                    0,
                ).label("total_inventory_value"),
                func.count(InventoryItem.id)
                .filter(InventoryItem.quantity <= InventoryItem.minimum_quantity)
                .label("low_stock_items"),
                func.count(func.distinct(InventoryItem.category)).label("categories"),
            )
        )

        row = result.one()

        return {
            "total_items": row.total_items or 0,
            "total_stock_units": (row.total_stock_units or 0),
            "total_inventory_value": float(row.total_inventory_value or 0),
            "low_stock_items": (row.low_stock_items or 0),
            "categories": row.categories or 0,
        }
