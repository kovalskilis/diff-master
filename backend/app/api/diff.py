from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import difflib

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import PatchedFragment, WorkspaceFile, Snapshot
from schemas.document import DiffResponse


import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

router = APIRouter()


@router.get("/diff", response_model=List[DiffResponse])
async def get_diff(
    workspace_file_id: Optional[int] = Query(None),
    snapshot_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-5: Get diff between before/after texts
    Returns list of all changes with difflib-generated HTML diff
    """
    fragments = []
    
    if workspace_file_id:
        # Get fragments by workspace file
        result = await session.execute(
            select(WorkspaceFile).where(
                WorkspaceFile.id == workspace_file_id,
                WorkspaceFile.user_id == user.id
            )
        )
        workspace_file = result.scalar_one_or_none()
        if not workspace_file:
            raise HTTPException(status_code=404, detail="Workspace file not found")
        
        # Get all patched fragments for this workspace file
        # Need to filter by edit_targets belonging to this workspace_file
        from models.document import EditTarget
        
        # First get all edit_target IDs for this workspace file
        result = await session.execute(
            select(EditTarget.id).where(
                EditTarget.workspace_file_id == workspace_file_id,
                EditTarget.user_id == user.id
            )
        )
        target_ids = [row[0] for row in result]
        
        if not target_ids:
            return []
        
        # Now get fragments for these targets
        result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.user_id == user.id,
                PatchedFragment.edit_target_id.in_(target_ids)
            )
        )
        fragments = result.scalars().fetchall()
    
    elif snapshot_id:
        # Get fragments by snapshot
        result = await session.execute(
            select(Snapshot).where(
                Snapshot.id == snapshot_id,
                Snapshot.user_id == user.id
            )
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        
        # Get all patched fragments for this snapshot
        result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.user_id == user.id
            )
        )
        fragments = result.scalars().fetchall()
    else:
        raise HTTPException(
            status_code=400, 
            detail="Either workspace_file_id or snapshot_id must be provided"
        )
    
    # Get all article data in one query
    from models.document import Article
    
    article_ids = [f.article_id for f in fragments if f.article_id]
    articles = {}
    
    if article_ids:
        result = await session.execute(
            select(Article).where(Article.id.in_(article_ids))
        )
        articles_query = result.scalars().fetchall()
        articles = {a.id: a for a in articles_query}
    
    # Generate diff for each fragment
    diff_list = []
    for fragment in fragments:
        # Generate HTML diff using difflib
        before_lines = (fragment.before_text or "").splitlines()
        after_lines = (fragment.after_text or "").splitlines()
        
        differ = difflib.HtmlDiff()
        diff_html = differ.make_table(
            before_lines,
            after_lines,
            fromdesc="Было",
            todesc="Стало",
            context=True,
            numlines=3
        )
        
        article = articles.get(fragment.article_id) if fragment.article_id else None
        
        diff_response = DiffResponse(
            article_id=fragment.article_id,
            title=article.title if article else None,
            article_number=article.article_number if article else None,
            before_text=fragment.before_text or "",
            after_text=fragment.after_text or "",
            change_type=fragment.change_type,
            diff_html=diff_html
        )
        diff_list.append(diff_response)
    
    return diff_list


@router.get("/diff/simple")
async def get_simple_diff(
    workspace_file_id: Optional[int] = Query(None),
    snapshot_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    Get simple unified diff (for text export)
    """
    fragments = []
    
    if workspace_file_id:
        result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.user_id == user.id
            )
        )
        fragments = result.scalars().fetchall()
    elif snapshot_id:
        result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.user_id == user.id
            )
        )
        fragments = result.scalars().fetchall()
    else:
        raise HTTPException(
            status_code=400,
            detail="Either workspace_file_id or snapshot_id must be provided"
        )
    
    diff_list = []
    for fragment in fragments:
        before_lines = (fragment.before_text or "").splitlines(keepends=True)
        after_lines = (fragment.after_text or "").splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"before_{fragment.tax_unit_id}",
            tofile=f"after_{fragment.tax_unit_id}",
            lineterm=''
        ))
        
        diff_list.append({
            "tax_unit_id": fragment.tax_unit_id,
            "title": fragment.tax_unit.title if fragment.tax_unit else None,
            "diff": '\n'.join(diff)
        })
    
    return diff_list

