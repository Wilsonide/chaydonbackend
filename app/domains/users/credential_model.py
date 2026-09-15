from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class UserCredential(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_credentials"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    password_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="credential",
    )
