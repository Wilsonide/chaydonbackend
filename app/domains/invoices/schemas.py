from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.invoices.models import InvoiceStatus


class InvoiceCreate(BaseModel):
    order_id: UUID
    subtotal: Decimal = Field(ge=0, decimal_places=2)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    tax: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class InvoiceCustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    email: str | None


class InvoiceOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    customer: InvoiceCustomerResponse


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    order: InvoiceOrderResponse

    subtotal: Decimal
    discount: Decimal
    tax: Decimal

    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal

    status: InvoiceStatus
