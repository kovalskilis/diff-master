from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
import uuid
from pydantic import BaseModel

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import BaseDocument, Article, Snapshot, AuditLog, AuditAction, ArticleVersion
from schemas.document import BaseDocumentResponse, ArticleResponse, TaxUnitHierarchyResponse
from services.audit_service import AuditService
from services.parsing import parse_document_structure, parse_txt_structure, extract_edits_for_review

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

router = APIRouter()


class ApprovedEditsRequest(BaseModel):
    articles: Dict[str, str]
    document_id: int


class ApprovedEditsResponse(BaseModel):
    task_id: str
    message: str


@router.post("/import", response_model=BaseDocumentResponse)
async def import_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-2: Import base document (.docx or .txt)
    Parses document into hierarchical tax_unit structure
    """
    if not file.filename.endswith(('.docx', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx and .txt files are supported"
        )
    
    # Read file content
    content = await file.read()
    source_type = "docx" if file.filename.endswith('.docx') else "txt"
    
    # Parse document structure for articles
    structure = None
    if source_type == "docx":
        structure = parse_document_structure(content)
    elif source_type == "txt":
        structure = parse_txt_structure(content.decode('utf-8'))
    
    # Create base document
    base_doc = BaseDocument(
        user_id=user.id,
        name=file.filename,
        source_type=source_type
    )
    session.add(base_doc)
    await session.flush()
    
    # Create Article records from structure
    if structure:
        for article_number, article_data in structure.items():
            article = Article(
                base_document_id=base_doc.id,
                article_number=article_number,
                title=article_data.get('title'),
                content=article_data.get('content', '')
            )
            session.add(article)
    
    await session.flush()
    
    # Create initial snapshot
    snapshot = Snapshot(
        user_id=user.id,
        base_document_id=base_doc.id,
        comment="Initial import"
    )
    session.add(snapshot)
    await session.flush()
    
    # Create versions for all articles
    if structure:
        for article_number, article_data in structure.items():
            # Get article
            result = await session.execute(
                select(Article).where(
                    Article.base_document_id == base_doc.id,
                    Article.article_number == article_number
                )
            )
            article = result.scalar_one_or_none()
            
            if article:
                version = ArticleVersion(
                    article_id=article.id,
                    snapshot_id=snapshot.id,
                    content=article_data.get('content', '')
                )
                session.add(version)
    
    # Audit log
    await AuditService.log_action(
        session, user.id, AuditAction.import_,
        entity_type="base_document",
        entity_id=base_doc.id,
        metadata={"filename": file.filename, "source_type": source_type}
    )
    
    await session.commit()
    await session.refresh(base_doc)
    
    # Return document with structure for frontend compatibility
    document_dict = {
        "id": base_doc.id,
        "name": base_doc.name,
        "source_type": base_doc.source_type,
        "imported_at": base_doc.imported_at,
        "structure": structure if structure else {}
    }
    
    
    return document_dict


@router.get("/documents", response_model=List[BaseDocumentResponse])
async def list_documents(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get all documents for current user"""
    result = await session.execute(
        select(BaseDocument).where(BaseDocument.user_id == user.id)
    )
    documents = result.scalars().all()
    
    # Build structure for each document
    document_list = []
    for doc in documents:
        try:
            # Get articles for this document
            articles_result = await session.execute(
                select(Article).where(Article.base_document_id == doc.id)
            )
            articles = articles_result.scalars().all()
            
            structure = {}
            for article in articles:
                structure[article.article_number] = {
                    "title": article.title or "",
                    "content": article.content
                }
            
            
            document_dict = {
                "id": doc.id,
                "name": doc.name,
                "source_type": doc.source_type,
                "imported_at": doc.imported_at,
                "structure": structure
            }
            document_list.append(document_dict)
        except Exception as e:
            print(f"Error loading structure for document {doc.id}: {e}")
            # Return document without structure
            document_dict = {
                "id": doc.id,
                "name": doc.name,
                "source_type": doc.source_type,
                "imported_at": doc.imported_at,
                "structure": {}
            }
            document_list.append(document_dict)
    
    return document_list


@router.get("/documents/{document_id}", response_model=BaseDocumentResponse)
async def get_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get specific document"""
    result = await session.execute(
        select(BaseDocument).where(
            BaseDocument.id == document_id,
            BaseDocument.user_id == user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    articles_result = await session.execute(
        select(Article).where(Article.base_document_id == document_id)
    )
    articles = articles_result.scalars().all()
    
    structure = {}
    if articles:
        for article in articles:
            structure[article.article_number] = {
                "title": article.title or "",
                "content": article.content
            }
    
    document_dict = {
        "id": document.id,
        "name": document.name,
        "source_type": document.source_type,
        "imported_at": document.imported_at,
        "structure": structure
    }
    
    return document_dict


@router.get("/documents/{document_id}/structure")
async def get_document_structure(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get document structure (compatibility endpoint - returns empty for new structure)"""
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
    
    # Return empty structure for compatibility (structure is now in /api/documents/{id})
    return []


@router.get("/documents/{document_id}/articles", response_model=List[ArticleResponse])
async def get_document_articles(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get all articles from document"""
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
    
    # Get all articles
    result = await session.execute(
        select(Article).where(Article.base_document_id == document_id)
    )
    articles = result.scalars().all()
    
    return articles


@router.post("/edits/extract")
async def extract_edits_from_file(
    file: UploadFile = File(...),
    user: User = Depends(current_active_user)
):
    """Extract edits from uploaded file for user review"""
    try:
        # Read file content
        content = await file.read()
        
        # Determine file type
        file_type = "txt"
        if file.filename and file.filename.lower().endswith('.docx'):
            file_type = "docx"
        
        # Extract edits by articles
        articles = extract_edits_for_review(content, file_type)
        
        return {
            "filename": file.filename,
            "file_type": file_type,
            "articles": articles,
            "total_articles": len([k for k in articles.keys() if k != "unknown"]),
            "has_unknown": "unknown" in articles
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error extracting edits: {str(e)}")


@router.post("/edits/process", response_model=ApprovedEditsResponse)
async def process_approved_edits(
    request: ApprovedEditsRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Process approved edits and start Phase 1 analysis"""
    try:
        # Verify document belongs to user
        result = await session.execute(
            select(BaseDocument).where(
                BaseDocument.id == request.document_id,
                BaseDocument.user_id == user.id
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Import the Celery task
        from worker.tasks import phase1_find_targets_approved
        
        # Start the task with approved edits
        task = phase1_find_targets_approved.delay(
            user_id=str(user.id),
            document_id=request.document_id,
            approved_articles=request.articles
        )
        
        return ApprovedEditsResponse(
            task_id=task.id,
            message="Edits processing started successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing approved edits: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Delete document and all related data"""
    result = await session.execute(
        select(BaseDocument).where(
            BaseDocument.id == document_id,
            BaseDocument.user_id == user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Use SQL to delete everything without loading objects into memory
    from sqlalchemy import text
    
    print(f"[DELETE] Starting deletion of document {document_id}")
    
    # Count records using SQL (without loading objects)
    workspace_count_result = await session.execute(
        text("SELECT COUNT(*) FROM workspace_file WHERE base_document_id = :doc_id").bindparams(doc_id=document_id)
    )
    workspace_count = workspace_count_result.scalar()
    
    import time
    
    # Delete all related data using SQL (fast, no object loading)
    start = time.time()
    print(f"[DELETE] Step 1/6: Deleting tax_unit_versions...")
    result = await session.execute(
        text("DELETE FROM tax_unit_version WHERE tax_unit_id IN (SELECT id FROM tax_unit WHERE base_document_id = :doc_id)").bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Step 1/6: Deleted tax_unit_versions in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Step 2/6: Deleting tax_units...")
    result = await session.execute(
        text("DELETE FROM tax_unit WHERE base_document_id = :doc_id").bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Step 2/6: Deleted tax_units in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Step 3/6: Deleting patched_fragments...")
    # First delete patched_fragments (they reference edit_target)
    result = await session.execute(
        text("DELETE FROM patched_fragment WHERE edit_target_id IN (SELECT id FROM edit_target WHERE workspace_file_id IN (SELECT id FROM workspace_file WHERE base_document_id = :doc_id))").bindparams(doc_id=document_id)
    )
    print(f"[DELETE] Step 3 result: {result.rowcount} patched_fragments deleted")
    # Also delete patched_fragments by article_id
    result = await session.execute(
        text("DELETE FROM patched_fragment WHERE article_id IN (SELECT id FROM article WHERE base_document_id = :doc_id)").bindparams(doc_id=document_id)
    )
    print(f"[DELETE] Step 3 result (articles): {result.rowcount} patched_fragments deleted")
    elapsed = time.time() - start
    print(f"[DELETE] Step 3/6: Deleted patched_fragments in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Step 4/6: Deleting edit_targets...")
    try:
        result = await session.execute(
            text("DELETE FROM edit_target WHERE workspace_file_id IN (SELECT id FROM workspace_file WHERE base_document_id = :doc_id)").bindparams(doc_id=document_id)
        )
        print(f"[DELETE] Step 4 result: {result.rowcount} rows affected")
    except Exception as e:
        print(f"[DELETE] Step 4 ERROR: {str(e)}")
        raise
    elapsed = time.time() - start
    print(f"[DELETE] Step 4/6: Deleted edit_targets in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Step 5/6: Deleting workspace_files...")
    result = await session.execute(
        text("DELETE FROM workspace_file WHERE base_document_id = :doc_id").bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Step 5/6: Deleted workspace_files in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Step 6/6: Deleting snapshots...")
    result = await session.execute(
        text("DELETE FROM snapshot WHERE base_document_id = :doc_id").bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Step 6/6: Deleted snapshots in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Final step: Deleting document...")
    await session.execute(
        text("DELETE FROM base_document WHERE id = :doc_id").bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Deleted document in {elapsed:.2f}s")
    
    # Audit log after deletion
    await AuditService.log_action(
        session, user.id, AuditAction.delete_,
        entity_type="base_document",
        entity_id=document_id,
        metadata={"workspace_files_count": workspace_count}
    )
    
    await session.commit()
    print(f"[DELETE] Document {document_id} deleted successfully")
    
    return {"message": "Document deleted successfully"}

