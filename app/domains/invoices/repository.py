from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.customers.models import Customer
from app.domains.invoices.models import Invoice
from app.domains.orders.models import Order
from app.shared.search import ilike_search


class InvoiceRepository:
    async def create(self, db: AsyncSession, invoice: Invoice) -> Invoice:
        db.add(invoice)
        await db.commit()

        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.id == invoice.id)
        )
        return result.scalar_one()

    async def get_by_id(self, db: AsyncSession, invoice_id: str):
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def get_by_order_id(self, db: AsyncSession, order_id: str):
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ):
        query = select(Invoice).join(Invoice.order).join(Order.customer)

        if search:
            query = query.where(
                or_(
                    ilike_search(search, Customer.name),
                    ilike_search(search, Order.title),
                )
            )

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.options(selectinload(Invoice.order).selectinload(Order.customer))
            .order_by(Invoice.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        return list(result.scalars().all()), total

    async def update(self, db: AsyncSession, invoice: Invoice):
        await db.commit()

        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.id == invoice.id)
        )
        return result.scalar_one()

    async def update_payment_state(self, db: AsyncSession, invoice: Invoice):
        await db.commit()

        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.id == invoice.id)
        )
        return result.scalar_one()
