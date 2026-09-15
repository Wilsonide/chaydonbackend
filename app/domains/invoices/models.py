import enum
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class InvoiceStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    VOID = "VOID"


class Invoice(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    tax: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    balance_due: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus),
        nullable=False,
        default=InvoiceStatus.UNPAID,
        index=True,
    )

    order = relationship(
        "Order",
        back_populates="invoice",
    )

    payments = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

    @property
    def order_title(self) -> str:
        return self.order.title
