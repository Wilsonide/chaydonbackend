from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import (
    RequireSuperAdminOrFrontDesk,
)
from app.domains.customers.schemas import (
    CustomerBalanceResponse,
    CustomerCreate,
    CustomerOrderResponse,
    CustomerResponse,
    CustomerUpdate,
)
from app.domains.customers.service import CustomerService
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)

service = CustomerService()


# ---------------------------------------------------------
# CREATE CUSTOMER
# ---------------------------------------------------------


@router.post(
    "",
    response_model=CustomerResponse,
)
async def create_customer(
    data: CustomerCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.create(
        db,
        data,
    )


# ---------------------------------------------------------
# GET CUSTOMERS
# ---------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
)
async def get_customers(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
    pagination: Pagination,
    search: str | None = None,
):
    return await service.get_all(
        db,
        pagination,
        search,
    )


# ---------------------------------------------------------
# GET CUSTOMER BY ID
# ---------------------------------------------------------


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
)
async def get_customer(
    customer_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_by_id(
        db,
        customer_id,
    )


# ---------------------------------------------------------
# UPDATE CUSTOMER
# ---------------------------------------------------------


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.update(
        db,
        customer_id,
        data,
    )


# ---------------------------------------------------------
# GET CUSTOMER ORDERS
# ---------------------------------------------------------


@router.get(
    "/{customer_id}/orders",
    response_model=list[CustomerOrderResponse],
)
async def get_customer_orders(
    customer_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_orders(
        db,
        customer_id,
    )


# ---------------------------------------------------------
# GET CUSTOMER BALANCE
# ---------------------------------------------------------


@router.get(
    "/{customer_id}/balance",
    response_model=CustomerBalanceResponse,
)
async def get_customer_balance(
    customer_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_balance(
        db,
        customer_id,
    )
