from datetime import UTC, datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.repository import CustomerRepository
from app.domains.invoices.models import (
    Invoice,
    InvoiceStatus,
)
from app.domains.invoices.repository import InvoiceRepository
from app.domains.orders.models import (
    Order,
    OrderFile,
    OrderStatus,
    OrderType,
)
from app.domains.orders.repository import OrderRepository
from app.domains.orders.schemas import (
    OrderCreate,
    OrderUpdate,
)
from app.domains.production.repository import ProductionRepository
from app.domains.users.models import (
    User,
    UserRole,
)
from app.services.cloudinary_service import CloudinaryService
from app.shared.responses import build_page


class OrderService:
    def __init__(self):
        self.repo = OrderRepository()
        self.customer_repo = CustomerRepository()
        self.invoice_repo = InvoiceRepository()
        self.production_repo = ProductionRepository()
        self.cloudinary = CloudinaryService()

    # ============================================================
    # CREATE ORDER
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        data: OrderCreate,
    ) -> Order:
        # --------------------------------------------------------
        # VERIFY CUSTOMER
        # --------------------------------------------------------
        customer = await self.customer_repo.get_by_id(
            db,
            str(data.customer_id),
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        try:
            # ----------------------------------------------------
            # DETERMINE INITIAL ORDER STATUS
            # ----------------------------------------------------
            initial_status = (
                OrderStatus.COMPLETED
                if data.order_type == OrderType.PRINT
                else OrderStatus.RECEIVED
            )

            # ----------------------------------------------------
            # CREATE ORDER
            # ----------------------------------------------------
            order = Order(
                customer_id=data.customer_id,
                order_type=data.order_type,
                title=data.title,
                description=data.description,
                status=initial_status,
                total_amount=data.total_amount,
                due_date=data.due_date,
            )

            if data.order_type == OrderType.PRINT:
                order.completed_at = datetime.now(UTC)

            db.add(order)
            await db.flush()

            # ----------------------------------------------------
            # CREATE INVOICE
            # ----------------------------------------------------
            invoice = Invoice(
                order_id=order.id,
                subtotal=data.total_amount,
                discount=0,
                tax=0,
                total_amount=data.total_amount,
                amount_paid=0,
                balance_due=data.total_amount,
                status=(
                    InvoiceStatus.PAID
                    if data.total_amount == 0
                    else InvoiceStatus.UNPAID
                ),
            )

            db.add(invoice)

            # ----------------------------------------------------
            # COMMIT ORDER + INVOICE TOGETHER
            # ----------------------------------------------------
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        # --------------------------------------------------------
        # RELOAD ORDER
        # --------------------------------------------------------
        created_order = await self.repo.get_by_id(
            db,
            str(order.id),
        )

        if not created_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order could not be loaded after creation",
            )

        return created_order

    # ============================================================
    # GET ALL ORDERS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search,
        status,
        order_type,
    ):
        items, total = await self.repo.get_all(
            db,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
            status=status,
            order_type=order_type,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    # ============================================================
    # GET ORDER BY ID
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        order = await self.repo.get_by_id(
            db,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return order

    # ============================================================
    # UPDATE ORDER
    # ============================================================

    async def update(
        self,
        db: AsyncSession,
        order_id: str,
        data: OrderUpdate,
    ):
        order = await self.get_by_id(
            db,
            order_id,
        )

        # --------------------------------------------------------
        # ORDER TYPE
        # --------------------------------------------------------
        #
        # DESIGN orders use the production/design workflow.
        #
        # PRINT orders bypass the production/design workflow.
        #
        # We allow changing the type only while the order has not
        # entered the production workflow AND no production folder
        # exists.
        #
        # The production-folder check is important because an order
        # could theoretically still have an early order status while
        # a production folder has already been created.
        #
        # Once a production folder exists, changing DESIGN ↔ PRINT
        # would invalidate the production workflow.
        # --------------------------------------------------------

        if data.order_type is not None:
            if data.order_type != order.order_type:
                # ------------------------------------------------
                # CHECK WHETHER PRODUCTION HAS STARTED
                # ------------------------------------------------

                production_folder = await self.production_repo.get_by_order_id(
                    db,
                    str(order.id),
                )

                if production_folder:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Order type cannot be changed because "
                            "a production folder already exists for this order."
                        ),
                    )

                # ------------------------------------------------
                # CHECK ORDER STATUS
                # ------------------------------------------------

                if order.status not in {
                    OrderStatus.RECEIVED,
                    OrderStatus.REVIEWING,
                }:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Order type cannot be changed "
                            "after the order has entered production."
                        ),
                    )

                order.order_type = data.order_type

        # --------------------------------------------------------
        # TITLE
        # --------------------------------------------------------

        if data.title is not None:
            order.title = data.title

        # --------------------------------------------------------
        # DESCRIPTION
        # --------------------------------------------------------

        if data.description is not None:
            order.description = data.description

        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------

        if data.status is not None:
            order.status = data.status

        # --------------------------------------------------------
        # DUE DATE
        # --------------------------------------------------------

        if data.due_date is not None:
            order.due_date = data.due_date

        # --------------------------------------------------------
        # UPDATE ORDER TOTAL + INVOICE
        # --------------------------------------------------------

        if data.total_amount is not None:
            invoice = await self.invoice_repo.get_by_order_id(
                db,
                order_id,
            )

            if invoice:
                if data.total_amount < invoice.amount_paid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Order total cannot be less than the amount already paid."
                        ),
                    )

                order.total_amount = data.total_amount

                invoice.subtotal = data.total_amount
                invoice.discount = 0
                invoice.tax = 0
                invoice.total_amount = data.total_amount

                invoice.balance_due = data.total_amount - invoice.amount_paid

                if data.total_amount in (
                    0,
                    invoice.amount_paid,
                ):
                    invoice.status = InvoiceStatus.PAID

                elif invoice.amount_paid > 0:
                    invoice.status = InvoiceStatus.PARTIALLY_PAID

                else:
                    invoice.status = InvoiceStatus.UNPAID

            else:
                order.total_amount = data.total_amount

        try:
            # ----------------------------------------------------
            # SAVE ORDER
            # ----------------------------------------------------

            await self.repo.update(
                db,
                order,
            )

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        # --------------------------------------------------------
        # RELOAD
        # --------------------------------------------------------

        updated_order = await self.repo.get_by_id(
            db,
            order_id,
        )

        if not updated_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return updated_order

    # ============================================================
    # UPLOAD ORDER FILE
    # ============================================================

    async def upload_file(
        self,
        db: AsyncSession,
        order_id: str,
        file: UploadFile,
        current_user: User,
    ):
        order = await self.get_by_id(
            db,
            order_id,
        )

        uploaded = None

        try:
            # ----------------------------------------------------
            # CLOUDINARY
            # ----------------------------------------------------

            uploaded = await self.cloudinary.upload(
                file=file,
                folder=f"printflow/orders/{order.id}",
            )

            # ----------------------------------------------------
            # DATABASE FILE
            # ----------------------------------------------------

            order_file = OrderFile(
                order_id=order.id,
                file_name=uploaded["file_name"],
                file_url=uploaded["url"],
                public_id=uploaded["public_id"],
                resource_type=uploaded["resource_type"],
                file_type=uploaded["file_type"],
                uploaded_by=current_user.id,
            )

            await self.repo.create_file(
                db,
                order_file,
            )

            await db.commit()

            return order_file

        except Exception:
            await db.rollback()

            # ----------------------------------------------------
            # CLEAN UP CLOUDINARY
            # ----------------------------------------------------

            if uploaded and uploaded.get("public_id"):
                try:
                    await self.cloudinary.delete(
                        public_id=uploaded["public_id"],
                        resource_type=uploaded.get("resource_type"),
                    )
                except Exception:
                    pass

            raise

    # ============================================================
    # GET ORDER FILES
    # ============================================================

    async def get_files(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        exists = await self.repo.exists(
            db,
            order_id,
        )

        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return await self.repo.get_files(
            db,
            order_id,
        )

    # ============================================================
    # DELETE ORDER FILE
    # ============================================================

    async def delete_file(
        self,
        db: AsyncSession,
        file_id: str,
        current_user: User,
    ):
        file = await self.repo.get_file(
            db,
            file_id,
        )

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        # --------------------------------------------------------
        # FRONT DESK OWNERSHIP
        # --------------------------------------------------------

        if (
            current_user.role == UserRole.FRONT_DESK
            and file.uploaded_by != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("You can only delete files you uploaded."),
            )

        try:
            # ----------------------------------------------------
            # CLOUDINARY
            # ----------------------------------------------------

            await self.cloudinary.delete(
                public_id=file.public_id,
                resource_type=file.resource_type,
            )

            # ----------------------------------------------------
            # DATABASE
            # ----------------------------------------------------

            await self.repo.delete_file(
                db,
                file,
            )

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        return {
            "message": "File deleted successfully",
        }

    # ============================================================
    # DELETE ORDER
    # ============================================================

    async def delete(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        # --------------------------------------------------------
        # LOAD ORDER + FILES
        # --------------------------------------------------------

        order = await self.get_by_id(
            db,
            order_id,
        )

        # --------------------------------------------------------
        # DELETE CLOUDINARY FILES
        # --------------------------------------------------------

        try:
            for file in order.files:
                await self.cloudinary.delete(
                    public_id=file.public_id,
                    resource_type=file.resource_type,
                )

            # ----------------------------------------------------
            # DELETE DATABASE ORDER
            # ----------------------------------------------------

            await self.repo.delete(
                db,
                order,
            )

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        return {
            "message": "Order deleted successfully",
        }
