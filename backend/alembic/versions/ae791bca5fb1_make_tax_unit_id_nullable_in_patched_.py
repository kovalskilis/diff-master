"""make_tax_unit_id_nullable_in_patched_fragment

Revision ID: ae791bca5fb1
Revises: c9d252bd1b98
Create Date: 2025-10-27 23:00:49.524007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae791bca5fb1'
down_revision: Union[str, None] = 'c9d252bd1b98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make tax_unit_id nullable in patched_fragment table
    op.alter_column('patched_fragment', 'tax_unit_id',
                   existing_type=sa.Integer(),
                   nullable=True)


def downgrade() -> None:
    # Before making column NOT NULL again, remove rows that would violate the constraint
    # (these rows were created while the column was nullable).
    op.execute("DELETE FROM patched_fragment WHERE tax_unit_id IS NULL")

    # Revert tax_unit_id to NOT NULL
    op.alter_column(
        'patched_fragment',
        'tax_unit_id',
        existing_type=sa.Integer(),
        nullable=False
    )
