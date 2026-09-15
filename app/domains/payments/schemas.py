from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.invoices.models import InvoiceStatus
from app.domains.payments.models import PaymentMethod


class PaymentCreate(BaseModel):
    order_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    method: PaymentMethod
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PaymentCustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    email: str | None


class PaymentOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    customer: PaymentCustomerResponse


class PaymentRecorderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    invoice_id: UUID

    order: PaymentOrderResponse
    recorder: PaymentRecorderResponse

    amount: Decimal
    method: PaymentMethod
    reference: str | None
    notes: str | None

    recorded_by: UUID
    created_at: datetime


class OrderPaymentSummary(BaseModel):
    order_id: UUID
    total_amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    status: InvoiceStatus
