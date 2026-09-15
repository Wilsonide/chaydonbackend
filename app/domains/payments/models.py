import enum
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    POS = "POS"
    OTHER = "OTHER"


class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    invoice_id: Mapped[str] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod),
        nullable=False,
    )

    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recorded_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    order = relationship(
        "Order",
        back_populates="payments",
    )

    invoice = relationship(
        "Invoice",
        back_populates="payments",
    )

    recorder = relationship(
        "User",
        foreign_keys=[recorded_by],
    )
