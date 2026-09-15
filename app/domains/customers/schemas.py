from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.invoices.models import InvoiceStatus
from app.domains.orders.models import OrderStatus


class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    email: str | None
    address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CustomerOrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    title: str
    description: str | None
    status: OrderStatus
    total_amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    created_at: datetime
    updated_at: datetime


class CustomerBalanceResponse(BaseModel):
    customer_id: UUID
    total_orders: int
    total_amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    status: InvoiceStatus
