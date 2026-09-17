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
                detail=("Invoice has not been created for this order."),
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
            recorded_by=recorder.id,
            recorder=recorder,
            order=order,
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
        # COMMIT PAYMENT + INVOICE TOGETHER
        # --------------------------------------------------------

        await db.commit()

        # --------------------------------------------------------
        # RETURN PAYMENT
        # --------------------------------------------------------
        #
        # PaymentRepository.create() already flushed the payment,
        # and the required relationships are attached above.
        #
        # expire_on_commit=False means the loaded objects remain
        # available after commit.
        # --------------------------------------------------------

        return payment

    # ============================================================
    # PAYMENT HISTORY
    # ============================================================

    async def get_order_payments(
        self,
        db: AsyncSession,
        order_id: str,
    ) -> list[Payment]:
        # Only verify that the order exists.
        # We don't need to load the complete order.
        order_exists = await self.order_repo.exists(
            db,
            order_id,
        )

        if not order_exists:
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

        # InvoiceRepository.get_by_id() already loads:
        #
        # invoice.order
        # invoice.order.customer
        #
        # So there is no need for two additional queries.

        order = invoice.order

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        customer = order.customer

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
