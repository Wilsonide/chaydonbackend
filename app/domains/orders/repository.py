from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.orders.models import (
    Order,
    OrderFile,
    OrderType,
)
from app.shared.search import ilike_search


class OrderRepository:
    # ============================================================
    # CREATE ORDER
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        order: Order,
    ) -> Order:
        db.add(order)
        await db.flush()
        return order

    # ============================================================
    # UPDATE ORDER
    # ============================================================

    async def update(
        self,
        db: AsyncSession,
        order: Order,
    ) -> Order:
        await db.flush()
        return order

    # ============================================================
    # GET SINGLE ORDER
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        order_id: str,
    ) -> Order | None:
        result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.files),
                selectinload(Order.customer),
            )
            .where(Order.id == order_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # GET ALL ORDERS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        status=None,
        order_type: OrderType | None = None,
    ):
        filters = []

        # --------------------------------------------------------
        # SEARCH
        # --------------------------------------------------------

        if search:
            search_filter = ilike_search(
                search,
                Order.title,
            )

            if search_filter is not None:
                filters.append(search_filter)

        # --------------------------------------------------------
        # STATUS FILTER
        # --------------------------------------------------------

        if status:
            filters.append(Order.status == status)

        # --------------------------------------------------------
        # ORDER TYPE FILTER
        # --------------------------------------------------------

        if order_type:
            filters.append(Order.order_type == order_type)

        # --------------------------------------------------------
        # COUNT
        # --------------------------------------------------------

        count_query = select(func.count(Order.id))

        if filters:
            count_query = count_query.where(*filters)

        total = await db.scalar(count_query)

        # --------------------------------------------------------
        # ORDERS
        # --------------------------------------------------------

        query = select(Order).options(
            selectinload(Order.files),
            selectinload(Order.customer),
        )

        if filters:
            query = query.where(*filters)

        query = (
            query.order_by(Order.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)

        orders = list(result.scalars().all())

        return orders, total or 0

    # ============================================================
    # CREATE ORDER FILE
    # ============================================================

    async def create_file(
        self,
        db: AsyncSession,
        file: OrderFile,
    ):
        db.add(file)
        await db.flush()
        return file

    # ============================================================
    # GET ORDER FILES
    # ============================================================

    async def get_files(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        result = await db.execute(
            select(OrderFile)
            .where(OrderFile.order_id == order_id)
            .order_by(OrderFile.created_at.desc())
        )

        return list(result.scalars().all())

    # ============================================================
    # GET SINGLE ORDER FILE
    # ============================================================

    async def get_file(
        self,
        db: AsyncSession,
        file_id: str,
    ):
        result = await db.execute(select(OrderFile).where(OrderFile.id == file_id))

        return result.scalar_one_or_none()

    # ============================================================
    # DELETE ORDER FILE
    # ============================================================

    async def delete_file(
        self,
        db: AsyncSession,
        file: OrderFile,
    ):
        await db.delete(file)
        await db.flush()

    # ============================================================
    # DELETE ORDER
    # ============================================================

    async def delete(
        self,
        db: AsyncSession,
        order: Order,
    ):
        await db.delete(order)
        await db.flush()

    # ============================================================
    # CHECK ORDER EXISTS
    # ============================================================

    async def exists(
        self,
        db: AsyncSession,
        order_id: str,
    ) -> bool:
        result = await db.scalar(select(Order.id).where(Order.id == order_id))

        return result is not None
