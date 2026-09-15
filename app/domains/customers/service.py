from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.models import Customer
from app.domains.customers.repository import CustomerRepository
from app.domains.customers.schemas import (
    CustomerCreate,
    CustomerUpdate,
)
from app.shared.responses import build_page


class CustomerService:
    def __init__(self):
        self.repo = CustomerRepository()

    async def create(
        self,
        db: AsyncSession,
        data: CustomerCreate,
    ) -> Customer:
        customer = Customer(
            name=data.name,
            phone=data.phone,
            email=data.email,
            address=data.address,
            notes=data.notes,
        )

        return await self.repo.create(
            db,
            customer,
        )

    async def get_by_id(
        self,
        db: AsyncSession,
        customer_id: str,
    ) -> Customer:
        customer = await self.repo.get_by_id(
            db,
            customer_id,
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        return customer

    async def update(
        self,
        db: AsyncSession,
        customer_id: str,
        data: CustomerUpdate,
    ) -> Customer:
        customer = await self.get_by_id(
            db,
            customer_id,
        )

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(
                customer,
                field,
                value,
            )

        return await self.repo.update(
            db,
            customer,
        )

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search,
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

    async def get_orders(
        self,
        db: AsyncSession,
        customer_id: str,
    ):
        await self.get_by_id(
            db,
            customer_id,
        )

        return await self.repo.get_orders(
            db,
            customer_id,
        )

    async def get_balance(
        self,
        db: AsyncSession,
        customer_id: str,
    ):
        await self.get_by_id(
            db,
            customer_id,
        )

        balance = await self.repo.get_balance(
            db,
            customer_id,
        )

        return {
            "customer_id": customer_id,
            **balance,
        }
