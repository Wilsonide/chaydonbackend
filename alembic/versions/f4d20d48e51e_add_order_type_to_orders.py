"""add order type to orders

Revision ID: f4d20d48e51e
Revises: 06a33792a468
Create Date: 2026-09-19 17:31:38.757150
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4d20d48e51e"
down_revision: Union[str, Sequence[str], None] = "06a33792a468"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    order_type_enum = sa.Enum(
        "DESIGN",
        "PRINT",
        name="ordertype",
    )

    # Create the PostgreSQL enum type first.
    order_type_enum.create(op.get_bind(), checkfirst=True)

    # Add the column temporarily as nullable so existing orders
    # can be populated safely.
    op.add_column(
        "orders",
        sa.Column(
            "order_type",
            order_type_enum,
            nullable=True,
        ),
    )

    # Existing orders follow the current production/design workflow.
    op.execute("UPDATE orders SET order_type = 'DESIGN' WHERE order_type IS NULL")

    # The column is now safe to make NOT NULL.
    op.alter_column(
        "orders",
        "order_type",
        existing_type=order_type_enum,
        nullable=False,
    )

    # Add an index for filtering DESIGN vs PRINT orders.
    op.create_index(
        op.f("ix_orders_order_type"),
        "orders",
        ["order_type"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_orders_order_type"),
        table_name="orders",
    )

    op.drop_column(
        "orders",
        "order_type",
    )

    # Remove the PostgreSQL enum type.
    sa.Enum(
        "DESIGN",
        "PRINT",
        name="ordertype",
    ).drop(
        op.get_bind(),
        checkfirst=True,
    )
