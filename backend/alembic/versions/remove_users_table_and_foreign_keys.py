"""remove users table and foreign keys

Revision ID: remove_users_fk
Revises: f1e2d3c4a1b2
Create Date: 2025-12-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'remove_users_fk'
down_revision: Union[str, None] = 'f1e2d3c4a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove all foreign key constraints to user table, then drop the user table.
    This migration removes authentication while keeping user_id columns as UUID.
    """
    # Drop all foreign key constraints that reference user.id
    # List of tables with foreign keys to user.id:
    tables_with_user_fk = [
        'base_document',
        'snapshot',
        'tax_unit_version',
        'workspace_file',
        'edit_target',
        'patched_fragment',
        'excel_report',
        'audit_log'
    ]
    
    # Drop foreign key constraints
    for table_name in tables_with_user_fk:
        # Get constraint name (PostgreSQL naming: {table}_{column}_fkey)
        constraint_name = f"{table_name}_user_id_fkey"
        try:
            op.drop_constraint(constraint_name, table_name, type_='foreignkey')
        except Exception as e:
            # Try alternative naming
            try:
                op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name} CASCADE;")
            except:
                pass
    
    # Also check for created_by_user_id in tax_unit_version
    try:
        op.drop_constraint('tax_unit_version_created_by_user_id_fkey', 'tax_unit_version', type_='foreignkey')
    except:
        try:
            op.execute("ALTER TABLE tax_unit_version DROP CONSTRAINT IF EXISTS tax_unit_version_created_by_user_id_fkey CASCADE;")
        except:
            pass
    
    # Drop the user table
    op.drop_table('user')
    
    # Drop the index on user.email if it exists
    op.execute("DROP INDEX IF EXISTS ix_user_email;")


def downgrade() -> None:
    """
    Recreate user table and foreign key constraints.
    Note: This will fail if there are existing user_id values that don't exist in user table.
    """
    # Recreate user table
    op.create_table('user',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=1024), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    
    # Recreate foreign key constraints
    op.create_foreign_key(
        'base_document_user_id_fkey',
        'base_document', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'snapshot_user_id_fkey',
        'snapshot', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'tax_unit_version_created_by_user_id_fkey',
        'tax_unit_version', 'user',
        ['created_by_user_id'], ['id']
    )
    op.create_foreign_key(
        'workspace_file_user_id_fkey',
        'workspace_file', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'edit_target_user_id_fkey',
        'edit_target', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'patched_fragment_user_id_fkey',
        'patched_fragment', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'excel_report_user_id_fkey',
        'excel_report', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'audit_log_user_id_fkey',
        'audit_log', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
