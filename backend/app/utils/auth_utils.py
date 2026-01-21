"""
Authentication utilities for handling dummy user when auth is disabled.
Since authentication is disabled, we only work with UUID values directly.
No User model is needed - user_id columns are just UUID fields.
"""
import uuid

# Fixed UUID for dummy user when auth is disabled
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def ensure_dummy_user(session):
    """
    Placeholder function for compatibility.
    Since auth is disabled and User table is removed, this function does nothing.
    The dummy user ID is used directly in all operations.
    """
    # No-op: user table doesn't exist, we just use DUMMY_USER_ID directly
    pass


def get_user_id() -> uuid.UUID:
    """
    Get the current user ID. When auth is disabled, returns DUMMY_USER_ID.
    """
    return DUMMY_USER_ID
