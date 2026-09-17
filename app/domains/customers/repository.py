from decimal import Decimal

from sqlalchemy import case, func, select
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

        return (
            list(result.scalars().all()),
            total or 0,
        )

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
        # For orders with an invoice, use invoice values.
        #
        # For orders without an invoice, use the order total
        # and assume nothing has been paid.

        total_amount_expr = case(
            (
                Invoice.id.is_not(None),
                Invoice.total_amount,
            ),
            else_=Order.total_amount,
        )

        amount_paid_expr = case(
            (
                Invoice.id.is_not(None),
                Invoice.amount_paid,
            ),
            else_=Decimal("0.00"),
        )

        balance_expr = case(
            (
                Invoice.id.is_not(None),
                Invoice.balance_due,
            ),
            else_=Order.total_amount,
        )

        result = await db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(
                    func.sum(total_amount_expr),
                    0,
                ).label("total_amount"),
                func.coalesce(
                    func.sum(amount_paid_expr),
                    0,
                ).label("amount_paid"),
                func.coalesce(
                    func.sum(balance_expr),
                    0,
                ).label("balance"),
            )
            .outerjoin(
                Invoice,
                Invoice.order_id == Order.id,
            )
            .where(Order.customer_id == customer_id)
        )

        row = result.one()

        total_orders = row.total_orders or 0
        total_amount = Decimal(row.total_amount or 0)
        amount_paid = Decimal(row.amount_paid or 0)
        balance = Decimal(row.balance or 0)

        if total_amount <= 0:
            payment_status = "UNPAID"

        elif balance <= 0:
            payment_status = "PAID"

        elif amount_paid <= 0:
            payment_status = "UNPAID"

        else:
            payment_status = "PARTIALLY_PAID"

        return {
            "total_orders": total_orders,
            "total_amount": total_amount,
            "amount_paid": amount_paid,
            "balance": balance,
            "status": payment_status,
        }
