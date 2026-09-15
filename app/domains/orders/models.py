import enum
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    REVIEWING = "REVIEWING"
    READY_FOR_PRODUCTION = "READY_FOR_PRODUCTION"
    IN_PRODUCTION = "IN_PRODUCTION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.RECEIVED,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    customer = relationship(
        "Customer",
        back_populates="orders",
    )
    files = relationship(
        "OrderFile",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    production_folder = relationship(
        "ProductionFolder",
        back_populates="order",
        uselist=False,
    )
    payments = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    invoice = relationship(
        "Invoice",
        back_populates="order",
        uselist=False,
    )


class OrderFile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_files"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    public_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="image",
    )

    uploaded_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    order = relationship(
        "Order",
        back_populates="files",
    )

    uploader = relationship("User")
