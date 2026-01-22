from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import difflib

from database import get_async_session
from models.document import PatchedFragment, WorkspaceFile, Snapshot, EditTarget, Article
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
    session: AsyncSession = Depends(get_async_session)
):
    """
    FR-5: Get diff between before/after texts
    Returns list of all changes with difflib-generated HTML diff
    """
    fragments = []
    
    if workspace_file_id:
        # Get fragments by workspace file
        result = await session.execute(
            select(WorkspaceFile).where(WorkspaceFile.id == workspace_file_id)
        )
        workspace_file = result.scalar_one_or_none()
        if not workspace_file:
            raise HTTPException(status_code=404, detail="Workspace file not found")
        
        # Get all patched fragments for this workspace file
        # Need to filter by edit_targets belonging to this workspace_file
        
        # First get all edit_target IDs for this workspace file
        result = await session.execute(
            select(EditTarget.id).where(
                EditTarget.workspace_file_id == workspace_file_id,
                EditTarget.id.isnot(None)
            )
        )
        target_ids = [row[0] for row in result]
        
        if not target_ids:
            return []
        
        # Now get fragments for these targets
        result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.id.isnot(None),
                PatchedFragment.edit_target_id.in_(target_ids)
            )
        )
        fragments = result.scalars().fetchall()
        
    elif snapshot_id:
        # Get fragments by snapshot
        result = await session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        
        # Get all patched fragments for this snapshot's document
        # Via edit_targets -> workspace_file -> base_document_id
        result = await session.execute(
            select(PatchedFragment)
            .join(EditTarget, PatchedFragment.edit_target_id == EditTarget.id)
            .join(WorkspaceFile, EditTarget.workspace_file_id == WorkspaceFile.id)
            .where(WorkspaceFile.base_document_id == snapshot.base_document_id)
        )
        fragments = result.scalars().fetchall()
    else:
        raise HTTPException(
            status_code=400, 
            detail="Either workspace_file_id or snapshot_id must be provided"
        )
    
    # Get all article data in one query
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
):
    """
    Get simple unified diff (for text export)
    """
    fragments = []
    
    if workspace_file_id:
        # Get fragments via edit_targets (same logic as get_diff)
        result = await session.execute(
            select(EditTarget.id).where(
                EditTarget.workspace_file_id == workspace_file_id
            )
        )
        target_ids = [row[0] for row in result]
        
        if not target_ids:
            return []
        
        result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.edit_target_id.in_(target_ids)
            )
        )
        fragments = result.scalars().fetchall()
        
    elif snapshot_id:
        # Get fragments via snapshot's document
        result = await session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        
        # Get fragments via edit_targets -> workspace_file -> base_document_id
        result = await session.execute(
            select(PatchedFragment)
            .join(EditTarget, PatchedFragment.edit_target_id == EditTarget.id)
            .join(WorkspaceFile, EditTarget.workspace_file_id == WorkspaceFile.id)
            .where(WorkspaceFile.base_document_id == snapshot.base_document_id)
        )
        fragments = result.scalars().fetchall()
    else:
        raise HTTPException(
            status_code=400,
            detail="Either workspace_file_id or snapshot_id must be provided"
        )
    
    # Get article data for fragments
    article_ids = [f.article_id for f in fragments if f.article_id]
    articles = {}
    
    if article_ids:
        result = await session.execute(
            select(Article).where(Article.id.in_(article_ids))
        )
        articles_query = result.scalars().fetchall()
        articles = {a.id: a for a in articles_query}
    
    diff_list = []
    for fragment in fragments:
        before_lines = (fragment.before_text or "").splitlines(keepends=True)
        after_lines = (fragment.after_text or "").splitlines(keepends=True)
        
        article = articles.get(fragment.article_id) if fragment.article_id else None
        article_num = article.article_number if article else "unknown"
        
        diff = list(difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"before_article_{article_num}",
            tofile=f"after_article_{article_num}",
            lineterm=''
        ))
        
        diff_list.append({
            "article_id": fragment.article_id,
            "article_number": article_num,
            "title": article.title if article else None,
            "diff": '\n'.join(diff)
        })
    
    return diff_list