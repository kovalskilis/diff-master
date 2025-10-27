from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
import uuid
from pydantic import BaseModel

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import BaseDocument, TaxUnit, TaxUnitVersion, Snapshot, AuditLog, AuditAction
from schemas.document import BaseDocumentResponse, TaxUnitResponse, TaxUnitHierarchyResponse
from services.document_parser import DocumentParser
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
        source_type=source_type,
        structure=structure
    )
    session.add(base_doc)
    await session.flush()
    
    # Parse document into tax units
    parser = DocumentParser()
    tax_units = await parser.parse_document(content, source_type, base_doc.id, user.id)
    
    for tax_unit in tax_units:
        session.add(tax_unit)
    
    # Create initial snapshot
    snapshot = Snapshot(
        user_id=user.id,
        base_document_id=base_doc.id,
        comment="Initial import"
    )
    session.add(snapshot)
    await session.flush()
    
    # Create versions for all tax units
    for tax_unit in tax_units:
        version = TaxUnitVersion(
            tax_unit_id=tax_unit.id,
            snapshot_id=snapshot.id,
            text_content=tax_unit.title or "",
            created_by_user_id=user.id
        )
        session.add(version)
        await session.flush()
        tax_unit.current_version_id = version.id
    
    # Audit log
    await AuditService.log_action(
        session, user.id, AuditAction.import_,
        entity_type="base_document",
        entity_id=base_doc.id,
        metadata={"filename": file.filename, "source_type": source_type}
    )
    
    await session.commit()
    await session.refresh(base_doc)
    
    return base_doc


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
    return documents


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
    
    return document


@router.get("/documents/{document_id}/structure", response_model=List[TaxUnitHierarchyResponse])
async def get_document_structure(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get hierarchical structure of document"""
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
    
    # Get all tax units
    result = await session.execute(
        select(TaxUnit).where(TaxUnit.base_document_id == document_id)
    )
    tax_units = result.scalars().all()
    
    # Build hierarchy
    units_by_id = {unit.id: unit for unit in tax_units}
    root_units = []
    
    for unit in tax_units:
        if unit.parent_id is None:
            root_units.append(unit)
    
    def build_tree(unit):
        children = [u for u in tax_units if u.parent_id == unit.id]
        return TaxUnitHierarchyResponse(
            id=unit.id,
            type=unit.type,
            title=unit.title,
            breadcrumbs_path=unit.breadcrumbs_path,
            children=[build_tree(child) for child in children]
        )
    
    return [build_tree(unit) for unit in root_units]


@router.get("/documents/{document_id}/articles")
async def get_document_articles(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get parsed articles structure from document"""
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
    
    return {
        "document_id": document_id,
        "structure": document.structure or {}
    }


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
    print(f"[DELETE] Step 3/6: Deleting edit_targets...")
    result = await session.execute(
        text("""
            DELETE FROM edit_target 
            WHERE workspace_file_id IN (
                SELECT id FROM workspace_file WHERE base_document_id = :doc_id
            )
        """).bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Step 3/6: Deleted edit_targets in {elapsed:.2f}s")
    
    start = time.time()
    print(f"[DELETE] Step 4/6: Deleting patched_fragments...")
    result = await session.execute(
        text("""
            DELETE FROM patched_fragment 
            WHERE edit_target_id IN (
                SELECT id FROM edit_target 
                WHERE workspace_file_id IN (
                    SELECT id FROM workspace_file WHERE base_document_id = :doc_id
                )
            )
        """).bindparams(doc_id=document_id)
    )
    elapsed = time.time() - start
    print(f"[DELETE] Step 4/6: Deleted patched_fragments in {elapsed:.2f}s")
    
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

