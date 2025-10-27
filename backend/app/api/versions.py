from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import Snapshot, BaseDocument, PatchedFragment, Article, ArticleVersion, AuditAction, EditTarget
from schemas.document import SnapshotResponse
from services.audit_service import AuditService


import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

router = APIRouter()


@router.get("/versions", response_model=List[SnapshotResponse])
async def list_versions(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-6: Get version history for document
    """
    # Verify document belongs to user
    result = await session.execute(
        select(BaseDocument).where(
            BaseDocument.id == document_id,
            BaseDocument.user_id == user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all snapshots
    result = await session.execute(
        select(Snapshot).where(
            Snapshot.base_document_id == document_id
        ).order_by(Snapshot.created_at.desc())
    )
    snapshots = result.scalars().all()
    
    return snapshots


@router.post("/versions/commit")
async def commit_version(
    workspace_file_id: int,
    comment: str = "",
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-4 Stage 3: Commit version (create snapshot)
    Creates new snapshot with all patched fragments
    """
    # Get all patched fragments for this workspace file
    # First get edit targets for this workspace file
    edit_targets_result = await session.execute(
        select(EditTarget).where(
            EditTarget.workspace_file_id == workspace_file_id,
            EditTarget.user_id == user.id
        )
    )
    edit_targets = edit_targets_result.scalars().all()
    
    if not edit_targets:
        raise HTTPException(status_code=400, detail="No edit targets found for this workspace file")
    
    # Get fragment IDs for these targets
    edit_target_ids = [et.id for et in edit_targets]
    
    # Get all patched fragments for these targets
    result = await session.execute(
        select(PatchedFragment).where(
            PatchedFragment.edit_target_id.in_(edit_target_ids)
        )
    )
    fragments = result.scalars().all()
    
    if not fragments:
        raise HTTPException(status_code=400, detail="No fragments to commit")
    
    # Get document ID from first fragment
    first_fragment = fragments[0]
    if not first_fragment.article_id:
        raise HTTPException(status_code=400, detail="Fragment has no article_id")
    
    # Explicitly load article to avoid MissingGreenlet
    article_result = await session.execute(
        select(Article).where(Article.id == first_fragment.article_id)
    )
    article = article_result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    document_id = article.base_document_id
    
    # Create new snapshot
    snapshot = Snapshot(
        user_id=user.id,
        base_document_id=document_id,
        comment=comment or f"Applied edits from workspace file {workspace_file_id}"
    )
    session.add(snapshot)
    await session.flush()
    
    # Create new versions for affected articles
    for fragment in fragments:
        # Create new version
        version = ArticleVersion(
            article_id=fragment.article_id,
            snapshot_id=snapshot.id,
            content=fragment.after_text
        )
        session.add(version)
    
    await session.flush()
    
    # Update articles content
    for fragment in fragments:
        if fragment.article_id:
            # Explicitly load article to update
            article_result = await session.execute(
                select(Article).where(Article.id == fragment.article_id)
            )
            article = article_result.scalar_one_or_none()
            if article:
                article.content = fragment.after_text
    
    # Audit log
    await AuditService.log_action(
        session, user.id, AuditAction.commit,
        entity_type="snapshot",
        entity_id=snapshot.id,
        metadata={
            "workspace_file_id": workspace_file_id,
            "fragments_count": len(fragments),
            "comment": comment
        }
    )
    
    await session.commit()
    await session.refresh(snapshot)
    
    return {
        "snapshot_id": snapshot.id,
        "message": f"Version committed successfully. {len(fragments)} fragments updated."
    }


@router.get("/versions/{snapshot_id}", response_model=SnapshotResponse)
async def get_version(
    snapshot_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get specific snapshot"""
    result = await session.execute(
        select(Snapshot).where(
            Snapshot.id == snapshot_id,
            Snapshot.user_id == user.id
        )
    )
    snapshot = result.scalar_one_or_none()
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return snapshot

