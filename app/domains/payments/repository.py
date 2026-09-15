from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.customers.models import Customer
from app.domains.orders.models import Order
from app.domains.payments.models import Payment
from app.shared.search import ilike_search


class PaymentRepository:
    async def create(
        self,
        db: AsyncSession,
        payment: Payment,
    ):
        db.add(payment)
        await db.flush()

        # Make sure relationships required by the response schema
        # are loaded before returning the payment.
        result = await db.execute(
            select(Payment)
            .options(
                selectinload(Payment.recorder),
                selectinload(Payment.order).selectinload(Order.customer),
            )
            .where(Payment.id == payment.id)
        )

        return result.scalar_one()

    async def get_by_id(
        self,
        db: AsyncSession,
        payment_id: str,
    ):
        result = await db.execute(
            select(Payment)
            .options(
                selectinload(Payment.recorder),
                selectinload(Payment.order).selectinload(Order.customer),
            )
            .where(Payment.id == payment_id)
        )

        return result.scalar_one_or_none()

    async def get_by_order_id(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        result = await db.execute(
            select(Payment)
            .options(
                selectinload(Payment.recorder),
                selectinload(Payment.order).selectinload(Order.customer),
            )
            .where(Payment.order_id == order_id)
            .order_by(Payment.created_at.desc())
        )

        return list(result.scalars().all())

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ):
        query = select(Payment).join(Payment.order).join(Order.customer)

        if search:
            query = query.where(
                or_(
                    ilike_search(search, Customer.name),
                    ilike_search(search, Order.title),
                )
            )

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.options(
                selectinload(Payment.recorder),
                selectinload(Payment.order).selectinload(Order.customer),
            )
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        return list(result.scalars().all()), total or 0
