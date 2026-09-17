from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.customers.models import Customer
from app.domains.invoices.models import Invoice
from app.domains.orders.models import Order
from app.shared.search import ilike_search


class InvoiceRepository:
    # ============================================================
    # CREATE INVOICE
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        invoice: Invoice,
    ) -> Invoice:
        db.add(invoice)

        await db.commit()

        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.id == invoice.id)
        )

        return result.scalar_one()

    # ============================================================
    # GET INVOICE BY ID
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        invoice_id: str,
    ):
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.id == invoice_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # GET INVOICE BY ORDER ID
    # ============================================================

    async def get_by_order_id(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
            .where(Invoice.order_id == order_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # GET ALL INVOICES
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ):
        filters = []

        if search:
            filters.append(
                or_(
                    ilike_search(
                        search,
                        Customer.name,
                    ),
                    ilike_search(
                        search,
                        Order.title,
                    ),
                )
            )

        # --------------------------------------------------------
        # TOTAL COUNT
        # --------------------------------------------------------

        count_query = (
            select(func.count(Invoice.id)).join(Invoice.order).join(Order.customer)
        )

        if filters:
            count_query = count_query.where(*filters)

        total = await db.scalar(count_query)

        # --------------------------------------------------------
        # PAGINATED DATA
        # --------------------------------------------------------

        query = (
            select(Invoice)
            .join(Invoice.order)
            .join(Order.customer)
            .options(selectinload(Invoice.order).selectinload(Order.customer))
        )

        if filters:
            query = query.where(*filters)

        query = (
            query.order_by(Invoice.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)

        invoices = list(result.scalars().all())

        return invoices, total or 0

    # ============================================================
    # UPDATE INVOICE
    # ============================================================

    async def update(
        self,
        db: AsyncSession,
        invoice: Invoice,
    ):
        await db.commit()
        await db.refresh(invoice)

        return invoice

    # ============================================================
    # UPDATE PAYMENT STATE
    # ============================================================

    async def update_payment_state(
        self,
        db: AsyncSession,
        invoice: Invoice,
    ):
        await db.commit()
        await db.refresh(invoice)

        return invoice
