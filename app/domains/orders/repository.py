from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.orders.models import Order, OrderFile
from app.shared.search import ilike_search


class OrderRepository:
    async def create(
        self,
        db: AsyncSession,
        order: Order,
    ) -> Order:
        db.add(order)

        await db.commit()

        result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.files),
                selectinload(Order.customer),
            )
            .where(Order.id == order.id)
        )

        return result.scalar_one()

    async def update(
        self,
        db: AsyncSession,
        order: Order,
    ) -> Order:
        await db.commit()

        result = await db.execute(
            select(Order)
            .options(
                selectinload(Order.files),
                selectinload(Order.customer),
            )
            .where(Order.id == order.id)
        )

        return result.scalar_one()

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

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        status=None,
    ):
        query = select(Order)

        if search:
            query = query.where(
                ilike_search(
                    search,
                    Order.title,
                )
            )

        if status:
            query = query.where(Order.status == status)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.options(
                selectinload(Order.files),
                selectinload(Order.customer),
            )
            .order_by(Order.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        return (
            list(result.scalars().all()),
            total,
        )

    async def create_file(
        self,
        db: AsyncSession,
        file: OrderFile,
    ):
        db.add(file)

        await db.commit()

        await db.refresh(file)

        return file

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

    async def get_file(
        self,
        db: AsyncSession,
        file_id: str,
    ):
        result = await db.execute(select(OrderFile).where(OrderFile.id == file_id))

        return result.scalar_one_or_none()

    async def delete_file(
        self,
        db: AsyncSession,
        file: OrderFile,
    ):
        await db.delete(file)

        await db.commit()

    async def delete(
        self,
        db: AsyncSession,
        order: Order,
    ):
        await db.delete(order)
        await db.commit()
