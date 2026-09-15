"""make timestamps timezone aware

Revision ID: fb6adeeba049
Revises: a2b873af20bb
Create Date: 2026-09-06 14:06:27.248078
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb6adeeba049"
down_revision: Union[str, Sequence[str], None] = "a2b873af20bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_TABLES = [
    "customers",
    "inventory_items",
    "invoices",
    "order_files",
    "orders",
    "payments",
    "production_activities",
    "production_files",
    "production_folders",
    "refresh_sessions",
    "stock_movements",
    "task_comments",
    "tasks",
    "users",
]


def upgrade() -> None:
    """Upgrade schema."""

    for table in TIMESTAMP_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN created_at
            TYPE TIMESTAMP WITH TIME ZONE
            USING created_at AT TIME ZONE 'UTC'
            """
        )

        op.execute(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN updated_at
            TYPE TIMESTAMP WITH TIME ZONE
            USING updated_at AT TIME ZONE 'UTC'
            """
        )


def downgrade() -> None:
    """Downgrade schema."""

    for table in TIMESTAMP_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN updated_at
            TYPE TIMESTAMP WITHOUT TIME ZONE
            USING updated_at AT TIME ZONE 'UTC'
            """
        )

        op.execute(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN created_at
            TYPE TIMESTAMP WITHOUT TIME ZONE
            USING created_at AT TIME ZONE 'UTC'
            """
        )
