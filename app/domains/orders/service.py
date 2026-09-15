from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.repository import CustomerRepository
from app.domains.invoices.models import Invoice, InvoiceStatus
from app.domains.invoices.repository import InvoiceRepository
from app.domains.orders.models import Order, OrderFile
from app.domains.orders.repository import OrderRepository
from app.domains.orders.schemas import (
    OrderCreate,
    OrderUpdate,
)
from app.domains.users.models import User, UserRole
from app.services.cloudinary_service import CloudinaryService
from app.shared.responses import build_page


class OrderService:
    def __init__(self):
        self.repo = OrderRepository()
        self.customer_repo = CustomerRepository()
        self.invoice_repo = InvoiceRepository()

        self.cloudinary = CloudinaryService()

    async def create(
        self,
        db: AsyncSession,
        data: OrderCreate,
    ) -> Order:
        customer = await self.customer_repo.get_by_id(
            db,
            str(data.customer_id),
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        order = Order(
            customer_id=data.customer_id,
            title=data.title,
            description=data.description,
            total_amount=data.total_amount,
            due_date=data.due_date,
        )

        db.add(order)

        await db.flush()

        invoice = Invoice(
            order_id=order.id,
            subtotal=data.total_amount,
            discount=0,
            tax=0,
            total_amount=data.total_amount,
            amount_paid=0,
            balance_due=data.total_amount,
            status=(
                InvoiceStatus.PAID if data.total_amount == 0 else InvoiceStatus.UNPAID
            ),
        )

        db.add(invoice)

        await db.commit()

        return await self.repo.get_by_id(
            db,
            str(order.id),
        )

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search,
        status,
    ):
        items, total = await self.repo.get_all(
            db,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
            status=status,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

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

        if data.title is not None:
            order.title = data.title

        if data.description is not None:
            order.description = data.description

        if data.status is not None:
            order.status = data.status

        if data.due_date is not None:
            order.due_date = data.due_date

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

                if data.total_amount in (0, invoice.amount_paid):
                    invoice.status = InvoiceStatus.PAID

                elif invoice.amount_paid > 0:
                    invoice.status = InvoiceStatus.PARTIALLY_PAID

                else:
                    invoice.status = InvoiceStatus.UNPAID

            else:
                order.total_amount = data.total_amount

        return await self.repo.update(
            db,
            order,
        )

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

        upload = await self.cloudinary.upload(
            file=file,
            folder=f"printflow/orders/{order.id}",
        )

        order_file = OrderFile(
            order_id=order.id,
            file_name=upload["file_name"],
            file_url=upload["url"],
            public_id=upload["public_id"],
            resource_type=upload["resource_type"],
            file_type=upload["file_type"],
            uploaded_by=current_user.id,
        )

        return await self.repo.create_file(
            db,
            order_file,
        )

    async def get_files(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        await self.get_by_id(
            db,
            order_id,
        )

        return await self.repo.get_files(
            db,
            order_id,
        )

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

        if (
            current_user.role == UserRole.FRONT_DESK
            and file.uploaded_by != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete files you uploaded.",
            )

        await self.cloudinary.delete(
            public_id=file.public_id,
            resource_type=file.resource_type,
        )

        await self.repo.delete_file(
            db,
            file,
        )

        return {
            "message": "File deleted successfully",
        }

    async def delete(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        order = await self.get_by_id(
            db,
            order_id,
        )

        # Delete all Cloudinary files belonging to the order
        for file in order.files:
            await self.cloudinary.delete(
                public_id=file.public_id,
                resource_type=file.resource_type,
            )

        # Delete the order and its database files
        await self.repo.delete(
            db,
            order,
        )

        return {
            "message": "Order deleted successfully",
        }
