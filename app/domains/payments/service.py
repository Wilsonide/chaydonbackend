from decimal import Decimal

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.repository import CustomerRepository
from app.domains.invoices.models import InvoiceStatus
from app.domains.invoices.repository import InvoiceRepository
from app.domains.orders.repository import OrderRepository
from app.domains.payments.invoice_pdf import InvoicePDF
from app.domains.payments.models import Payment
from app.domains.payments.repository import PaymentRepository
from app.domains.payments.schemas import (
    OrderPaymentSummary,
    PaymentCreate,
)
from app.domains.users.repository import UserRepository
from app.shared.responses import build_page

pdf_generator = InvoicePDF()


class PaymentService:
    def __init__(self):
        self.repo = PaymentRepository()
        self.order_repo = OrderRepository()
        self.invoice_repo = InvoiceRepository()
        self.customer_repo = CustomerRepository()
        self.user_repo = UserRepository()

    # ============================================================
    # RECORD PAYMENT
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        data: PaymentCreate,
        user_id: str,
    ):
        # --------------------------------------------------------
        # GET ORDER
        # --------------------------------------------------------

        order = await self.order_repo.get_by_id(
            db,
            data.order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # --------------------------------------------------------
        # GET INVOICE
        # --------------------------------------------------------

        invoice = await self.invoice_repo.get_by_order_id(
            db,
            data.order_id,
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice has not been created for this order.",
            )

        # --------------------------------------------------------
        # GET RECORDER
        # --------------------------------------------------------

        recorder = await self.user_repo.get_by_id(
            db,
            user_id,
        )

        if not recorder:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Recording user could not be found.",
            )

        if not recorder.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # --------------------------------------------------------
        # CHECK BALANCE
        # --------------------------------------------------------

        if data.amount > invoice.balance_due:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(f"Outstanding balance is {invoice.balance_due:.2f}"),
            )

        # --------------------------------------------------------
        # CREATE PAYMENT
        # --------------------------------------------------------

        payment = Payment(
            order_id=data.order_id,
            invoice_id=invoice.id,
            amount=data.amount,
            method=data.method,
            reference=data.reference,
            notes=data.notes,
            # Keep the foreign-key value.
            recorded_by=recorder.id,
            # Explicitly attach the User relationship.
            recorder=recorder,
        )

        await self.repo.create(
            db,
            payment,
        )

        # --------------------------------------------------------
        # UPDATE INVOICE
        # --------------------------------------------------------

        invoice.amount_paid += data.amount
        invoice.balance_due -= data.amount

        if invoice.balance_due == Decimal("0.00"):
            invoice.status = InvoiceStatus.PAID

        elif invoice.amount_paid > Decimal("0.00"):
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        else:
            invoice.status = InvoiceStatus.UNPAID

        # --------------------------------------------------------
        # COMMIT
        # --------------------------------------------------------

        await db.commit()

        # --------------------------------------------------------
        # RELOAD PAYMENT WITH REQUIRED RELATIONSHIPS
        # --------------------------------------------------------

        payment = await self.repo.get_by_id(
            db,
            payment.id,
        )

        if not payment:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=("Payment was created but could not be retrieved."),
            )

        # --------------------------------------------------------
        # SAFETY CHECK
        # --------------------------------------------------------

        if not payment.recorder:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Payment was created, but the recording user could not be loaded."
                ),
            )

        return payment

    # ============================================================
    # PAYMENT HISTORY
    # ============================================================

    async def get_order_payments(
        self,
        db: AsyncSession,
        order_id: str,
    ) -> list[Payment]:
        order = await self.order_repo.get_by_id(
            db,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return await self.repo.get_by_order_id(
            db,
            order_id,
        )

    # ============================================================
    # PAYMENT SUMMARY
    # ============================================================

    async def get_order_summary(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        invoice = await self.invoice_repo.get_by_order_id(
            db,
            order_id,
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )

        return OrderPaymentSummary(
            order_id=order_id,
            total_amount=invoice.total_amount,
            amount_paid=invoice.amount_paid,
            balance=invoice.balance_due,
            status=invoice.status,
        )

    # ============================================================
    # DOWNLOAD INVOICE
    # ============================================================

    async def download_invoice(
        self,
        db: AsyncSession,
        invoice_id: str,
    ):
        invoice = await self.invoice_repo.get_by_id(
            db,
            invoice_id,
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )

        order = await self.order_repo.get_by_id(
            db,
            invoice.order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        customer = await self.customer_repo.get_by_id(
            db,
            order.customer_id,
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        pdf = pdf_generator.generate(
            invoice,
            order,
            customer,
        )

        return StreamingResponse(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="invoice-{invoice.id}.pdf"'
                ),
            },
        )

    # ============================================================
    # ALL PAYMENTS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search: str | None = None,
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
