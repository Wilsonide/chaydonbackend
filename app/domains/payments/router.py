from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import (
    RequireFrontDesk,
    RequireSuperAdminOrFrontDesk,
)
from app.domains.payments.schemas import (
    OrderPaymentSummary,
    PaymentCreate,
    PaymentResponse,
)
from app.domains.payments.service import PaymentService
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)

service = PaymentService()


# ============================================================
# PAYMENT LIST
# ============================================================


@router.get("", response_model=PaginatedResponse[PaymentResponse])
async def get_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[object, Depends(RequireSuperAdminOrFrontDesk)],
    pagination: Pagination,
    search: str | None = None,
):
    return await service.get_all(
        db,
        pagination,
        search,
    )


# ============================================================
# RECORD PAYMENT
# ============================================================


@router.post(
    "",
    response_model=PaymentResponse,
)
async def create_payment(
    data: PaymentCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireFrontDesk),
    ],
):
    return await service.create(
        db,
        data,
        str(current_user.id),
    )


# ============================================================
# PAYMENT HISTORY FOR ORDER
# ============================================================


@router.get(
    "/order/{order_id}",
    response_model=list[PaymentResponse],
)
async def get_order_payments(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_order_payments(
        db,
        order_id,
    )


# ============================================================
# ORDER PAYMENT SUMMARY
# ============================================================


@router.get(
    "/order/{order_id}/summary",
    response_model=OrderPaymentSummary,
)
async def get_order_payment_summary(
    order_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.get_order_summary(
        db,
        order_id,
    )


# ============================================================
# DOWNLOAD INVOICE
# ============================================================


@router.get(
    "/invoice/{invoice_id}/download",
)
async def download_invoice(
    invoice_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrFrontDesk),
    ],
):
    return await service.download_invoice(
        db,
        invoice_id,
    )
