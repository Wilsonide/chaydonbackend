"""fix update

Revision ID: a64e6113f538
Revises: 39f7ffa113bf
Create Date: 2026-09-12 16:51:37.938392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a64e6113f538'
down_revision: Union[str, Sequence[str], None] = '39f7ffa113bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
