"""
Authentication utilities for handling dummy user when auth is disabled
"""
import uuid
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Fixed UUID for dummy user when auth is disabled
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def ensure_dummy_user(session: AsyncSession) -> None:
    """
    Placeholder for dummy user creation.
    With user table removed, this function is a no-op.
    """
    pass


def get_user_id() -> uuid.UUID:
    """
    Get the current user ID. When auth is disabled, returns DUMMY_USER_ID.
    """
    return DUMMY_USER_ID
