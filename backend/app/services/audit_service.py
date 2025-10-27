from sqlalchemy.ext.asyncio import AsyncSession
from models.document import AuditLog, AuditAction
import uuid
from typing import Optional, Dict, Any


class AuditService:
    @staticmethod
    async def log_action(
        session: AsyncSession,
        user_id: uuid.UUID,
        action: AuditAction,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log user action to audit log"""
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {}
        )
        session.add(audit_entry)
        return audit_entry

