"""fix_auditaction_delete_value

Revision ID: 26dc64b9fc90
Revises: 0661cc543d6d
Create Date: 2025-10-26 14:10:34.132167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26dc64b9fc90'
down_revision: Union[str, None] = '0661cc543d6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: The enum value already exists in the database from previous migration
    # We just need to ensure it's using the correct value
    # No need to alter enum, as 'delete_' already exists in database
    pass


def downgrade() -> None:
    # No need to downgrade
    pass
