from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import RequireSuperAdminOrFrontDesk
from app.domains.invoices.schemas import (
    InvoiceCreate,
    InvoiceResponse,
)
from app.domains.invoices.service import InvoiceService
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"],
)

service = InvoiceService()


# ============================================================
# CREATE INVOICE
# ============================================================


@router.post(
    "",
    response_model=InvoiceResponse,
)
async def create_invoice(
    data: InvoiceCreate,
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


# ============================================================
# GET ALL INVOICES
# ============================================================


@router.get(
    "",
    response_model=PaginatedResponse[InvoiceResponse],
)
async def get_invoices(
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


# ============================================================
# GET SINGLE INVOICE
# ============================================================


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
)
async def get_invoice(
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
    return await service.get_by_id(
        db,
        invoice_id,
    )


# ============================================================
# GET INVOICE BY ORDER
# ============================================================


@router.get(
    "/order/{order_id}",
    response_model=InvoiceResponse,
)
async def get_invoice_by_order(
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
    return await service.get_by_order_id(
        db,
        order_id,
    )
