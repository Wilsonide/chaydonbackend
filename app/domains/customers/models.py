from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    orders = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
