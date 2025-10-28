"""add unique index to prevent duplicate edit targets

Revision ID: f1e2d3c4a1b2
Revises: ae791bca5fb1
Create Date: 2025-10-28 00:00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4a1b2'
down_revision: Union[str, None] = 'ae791bca5fb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize instruction_text by collapsing whitespace before deduplication
    # 1) Remove duplicates based on normalized text (keep lowest id)
    op.execute(
        """
        WITH d AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id,
                                    workspace_file_id,
                                    md5(regexp_replace(instruction_text, '\\s+', ' ', 'g'))
                       ORDER BY id
                   ) rn
            FROM edit_target
        )
        DELETE FROM edit_target e
        USING d
        WHERE e.id = d.id AND d.rn > 1;
        """
    )

    # 2) Drop legacy exact-text unique index if был создан вручную
    op.execute("DROP INDEX IF EXISTS uq_edit_target_unique;")

    # 3) Create functional unique index on normalized text (idempotent)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_edit_target_norm
        ON edit_target (
            user_id,
            workspace_file_id,
            md5(regexp_replace(instruction_text, '\\s+', ' ', 'g'))
        );
        """
    )

    # 4) Create partial unique index when article_id is known (more strict)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_edit_target_article
        ON edit_target (user_id, workspace_file_id, article_id)
        WHERE article_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    # Drop the functional unique index if it exists
    op.execute("DROP INDEX IF EXISTS uq_edit_target_norm;")
    op.execute("DROP INDEX IF EXISTS uq_edit_target_article;")


