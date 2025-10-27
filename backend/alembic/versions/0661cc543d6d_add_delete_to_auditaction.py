"""add_delete_to_auditaction

Revision ID: 0661cc543d6d
Revises: 09f93edb554c
Create Date: 2025-10-26 13:43:44.668562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0661cc543d6d'
down_revision: Union[str, None] = '09f93edb554c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'delete_' to the auditaction enum
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'delete_'")

def downgrade() -> None:
    # Note: Cannot remove enum values in PostgreSQL, this is a no-op
    pass
