from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.invoices.models import (
    Invoice,
    InvoiceStatus,
)
from app.domains.invoices.repository import InvoiceRepository
from app.domains.invoices.schemas import InvoiceCreate
from app.domains.orders.repository import OrderRepository
from app.shared.responses import build_page


class InvoiceService:
    def __init__(self):
        self.repo = InvoiceRepository()
        self.order_repo = OrderRepository()

    # ============================================================
    # CREATE INVOICE
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        data: InvoiceCreate,
    ) -> Invoice:
        # Lightweight existence check.
        # We do not need the full Order object here.
        order_exists = await self.order_repo.exists(
            db,
            data.order_id,
        )

        if not order_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        total_amount = data.subtotal - data.discount + data.tax

        if total_amount < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice total cannot be negative",
            )

        amount_paid = Decimal("0.00")
        balance_due = total_amount

        if total_amount == Decimal("0.00"):
            invoice_status = InvoiceStatus.PAID
        else:
            invoice_status = InvoiceStatus.UNPAID

        invoice = Invoice(
            order_id=data.order_id,
            subtotal=data.subtotal,
            discount=data.discount,
            tax=data.tax,
            total_amount=total_amount,
            amount_paid=amount_paid,
            balance_due=balance_due,
            status=invoice_status,
        )

        return await self.repo.create(
            db,
            invoice,
        )

    # ============================================================
    # GET ALL INVOICES
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search: str | None,
    ):
        items, total = await self.repo.get_all(
            db,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    # ============================================================
    # GET INVOICE BY ID
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        invoice_id: str,
    ) -> Invoice:
        invoice = await self.repo.get_by_id(
            db,
            invoice_id,
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )

        return invoice

    # ============================================================
    # GET INVOICE BY ORDER
    # ============================================================

    async def get_by_order_id(
        self,
        db: AsyncSession,
        order_id: str,
    ) -> Invoice:
        invoice = await self.repo.get_by_order_id(
            db,
            order_id,
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found for this order",
            )

        return invoice
