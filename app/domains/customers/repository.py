from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.models import Customer
from app.domains.invoices.models import Invoice
from app.domains.orders.models import Order
from app.shared.search import ilike_search


class CustomerRepository:
    async def create(
        self,
        db: AsyncSession,
        customer: Customer,
    ) -> Customer:
        db.add(customer)
        await db.commit()
        await db.refresh(customer)

        return customer

    async def get_by_id(
        self,
        db: AsyncSession,
        customer_id: str,
    ) -> Customer | None:
        result = await db.execute(select(Customer).where(Customer.id == customer_id))

        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        customer: Customer,
    ) -> Customer:
        await db.commit()
        await db.refresh(customer)

        return customer

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ):
        query = select(Customer)

        if search:
            query = query.where(
                ilike_search(
                    search,
                    Customer.name,
                    Customer.phone,
                )
            )

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.order_by(Customer.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        return list(result.scalars()), total

    async def get_orders(
        self,
        db: AsyncSession,
        customer_id: str,
    ):
        result = await db.execute(
            select(
                Order,
                Invoice,
            )
            .outerjoin(
                Invoice,
                Invoice.order_id == Order.id,
            )
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
        )

        orders = []

        for order, invoice in result.all():
            if invoice:
                total_amount = Decimal(invoice.total_amount or 0)

                amount_paid = Decimal(invoice.amount_paid or 0)

                balance = Decimal(invoice.balance_due or 0)

            else:
                total_amount = Decimal(order.total_amount or 0)

                amount_paid = Decimal("0.00")

                balance = total_amount

            orders.append(
                {
                    "id": order.id,
                    "customer_id": order.customer_id,
                    "title": order.title,
                    "description": order.description,
                    "status": order.status,
                    "total_amount": total_amount,
                    "amount_paid": amount_paid,
                    "balance": balance,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                }
            )

        return orders

    async def get_balance(
        self,
        db: AsyncSession,
        customer_id: str,
    ):
        result = await db.execute(
            select(
                Order,
                Invoice,
            )
            .outerjoin(
                Invoice,
                Invoice.order_id == Order.id,
            )
            .where(Order.customer_id == customer_id)
        )

        rows = result.all()

        total_orders = len(rows)

        total_amount = Decimal("0.00")
        amount_paid = Decimal("0.00")
        balance = Decimal("0.00")

        for order, invoice in rows:
            if invoice:
                order_total = Decimal(invoice.total_amount or 0)

                order_paid = Decimal(invoice.amount_paid or 0)

                order_balance = Decimal(invoice.balance_due or 0)

            else:
                order_total = Decimal(order.total_amount or 0)

                order_paid = Decimal("0.00")

                order_balance = order_total

            total_amount += order_total
            amount_paid += order_paid
            balance += order_balance

        if total_amount <= 0:
            status = "UNPAID"

        elif balance <= 0:
            status = "PAID"

        elif amount_paid <= 0:
            status = "UNPAID"

        else:
            status = "PARTIALLY_PAID"

        return {
            "total_orders": total_orders,
            "total_amount": total_amount,
            "amount_paid": amount_paid,
            "balance": balance,
            "status": status,
        }
