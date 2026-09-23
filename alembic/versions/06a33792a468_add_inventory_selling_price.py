"""add inventory selling price

Revision ID: 06a33792a468
Revises: 02cdcc69cac6
Create Date: 2026-09-19 11:38:55.216982

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "06a33792a468"
down_revision: Union[str, Sequence[str], None] = "02cdcc69cac6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add the columns temporarily as nullable so existing rows
    # can be populated safely.
    op.add_column(
        "inventory_items",
        sa.Column(
            "unit_selling_price",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )

    op.add_column(
        "stock_movements",
        sa.Column(
            "unit_selling_price",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )

    # Existing inventory items do not have a selling price yet.
    # Initialize them to 0.00.
    op.execute(
        """
        UPDATE inventory_items
        SET unit_selling_price = 0
        WHERE unit_selling_price IS NULL
        """
    )

    # Existing stock movements also need a value.
    op.execute(
        """
        UPDATE stock_movements
        SET unit_selling_price = 0
        WHERE unit_selling_price IS NULL
        """
    )

    # Now that every existing row has a value, enforce NOT NULL.
    op.alter_column(
        "inventory_items",
        "unit_selling_price",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )

    op.alter_column(
        "stock_movements",
        "unit_selling_price",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "stock_movements",
        "unit_selling_price",
    )

    op.drop_column(
        "inventory_items",
        "unit_selling_price",
    )
