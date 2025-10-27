from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from typing import List

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import Article, ArticleVersion, BaseDocument
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
    Searches in article titles and content
    """
    if not q:
        return []
    
    # Build query with FTS
    base_query = select(Article).where(Article.base_document_id.in_(
        select(BaseDocument.id).where(BaseDocument.user_id == user.id)
    ))
    
    if document_id:
        base_query = base_query.where(Article.base_document_id == document_id)
    
    # PostgreSQL FTS query (Russian language)
    # Note: This requires fulltext_vector to be populated
    fts_query = base_query.where(
        text("fulltext_vector @@ plainto_tsquery('russian', :query)")
    ).params(query=q).limit(limit)
    
    result = await session.execute(fts_query)
    articles = result.scalars().all()
    
    search_results = []
    for article in articles:
        # Create snippet (first 200 chars)
        snippet = article.content[:200] + "..." if len(article.content) > 200 else article.content
        
        search_results.append(SearchResult(
            article_id=article.id,
            title=article.title,
            article_number=article.article_number,
            text_snippet=snippet,
            rank=1.0  # Can be enhanced with ts_rank
        ))
    
    return search_results


@router.get("/search/articles", response_model=List[SearchResult])
async def search_articles_simple(
    q: str = Query(..., min_length=1),
    document_id: int = Query(...),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    Simple search for articles by title/article_number (for dropdown in Review Stage)
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
    query = select(Article).where(
        Article.base_document_id == document_id
    ).where(
        (Article.title.ilike(f"%{q}%")) | 
        (Article.article_number.ilike(f"%{q}%")) |
        (Article.content.ilike(f"%{q}%"))
    ).limit(limit)
    
    result = await session.execute(query)
    articles = result.scalars().all()
    
    search_results = []
    for article in articles:
        search_results.append(SearchResult(
            article_id=article.id,
            title=article.title or "",
            article_number=article.article_number,
            text_snippet=article.content[:200] if len(article.content) > 200 else article.content,
            rank=1.0
        ))
    
    return search_results

