from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from typing import List

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import TaxUnit, TaxUnitVersion, BaseDocument
from schemas.document import SearchResult


import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

router = APIRouter()


@router.get("/search", response_model=List[SearchResult])
async def search_documents(
    q: str = Query(..., min_length=2),
    document_id: int = Query(None),
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-7: Full-text search using PostgreSQL FTS
    Searches in tax_unit titles and current version text
    """
    if not q:
        return []
    
    # Build query with FTS
    base_query = select(TaxUnit).where(TaxUnit.base_document_id.in_(
        select(BaseDocument.id).where(BaseDocument.user_id == user.id)
    ))
    
    if document_id:
        base_query = base_query.where(TaxUnit.base_document_id == document_id)
    
    # PostgreSQL FTS query (Russian language)
    # Note: This requires fulltext_vector to be populated
    fts_query = base_query.where(
        text("fulltext_vector @@ plainto_tsquery('russian', :query)")
    ).params(query=q).limit(limit)
    
    result = await session.execute(fts_query)
    tax_units = result.scalars().all()
    
    search_results = []
    for unit in tax_units:
        # Get current version text
        version = None
        if unit.current_version_id:
            version_result = await session.execute(
                select(TaxUnitVersion).where(TaxUnitVersion.id == unit.current_version_id)
            )
            version = version_result.scalar_one_or_none()
        
        text_content = version.text_content if version else unit.title or ""
        
        # Create snippet (first 200 chars)
        snippet = text_content[:200] + "..." if len(text_content) > 200 else text_content
        
        search_results.append(SearchResult(
            tax_unit_id=unit.id,
            title=unit.title,
            breadcrumbs_path=unit.breadcrumbs_path,
            text_snippet=snippet,
            rank=1.0  # Can be enhanced with ts_rank
        ))
    
    return search_results


@router.get("/search/tax-units", response_model=List[SearchResult])
async def search_tax_units_simple(
    q: str = Query(..., min_length=1),
    document_id: int = Query(...),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    Simple search for tax units by title/breadcrumbs (for dropdown in Review Stage)
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
    
    # Simple ILIKE search
    query = select(TaxUnit).where(
        TaxUnit.base_document_id == document_id
    ).where(
        (TaxUnit.title.ilike(f"%{q}%")) | 
        (TaxUnit.breadcrumbs_path.ilike(f"%{q}%"))
    ).limit(limit)
    
    result = await session.execute(query)
    tax_units = result.scalars().all()
    
    search_results = []
    for unit in tax_units:
        search_results.append(SearchResult(
            tax_unit_id=unit.id,
            title=unit.title or "",
            breadcrumbs_path=unit.breadcrumbs_path or "",
            text_snippet=unit.title or "",
            rank=1.0
        ))
    
    return search_results

