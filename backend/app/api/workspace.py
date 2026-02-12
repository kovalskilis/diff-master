from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from database import get_async_session
from models.document import WorkspaceFile, BaseDocument, AuditAction
from schemas.document import WorkspaceFileResponse
from services.audit_service import AuditService


import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

router = APIRouter()


@router.post("/workspace/file", response_model=WorkspaceFileResponse)
async def upload_workspace_file(
    base_document_id: int = Form(...),
    file: Optional[UploadFile] = File(None),
    text_content: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_async_session)
):
    """
    FR-3: Upload edit file (.docx, .txt, or plain text)
    This only uploads the file, does not trigger LLM processing
    """
    # Verify document exists
    result = await session.execute(
        select(BaseDocument).where(
            BaseDocument.id == base_document_id,
            
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    workspace_file = WorkspaceFile(
        
        base_document_id=base_document_id
    )
    
    if file:
        # File upload
        content = await file.read()
        workspace_file.filename = file.filename
        workspace_file.source_type = "file"
        
        # Validate file type for edits
        if file.filename and file.filename.lower().endswith('.txt'):
            # Text file - try to decode
            try:
                workspace_file.raw_payload_text = content.decode('utf-8')
            except UnicodeDecodeError:
                # Try other encodings
                for encoding in ['cp1251', 'windows-1251', 'latin1']:
                    try:
                        workspace_file.raw_payload_text = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail="РќРµ СѓРґР°Р»РѕСЃСЊ РґРµРєРѕРґРёСЂРѕРІР°С‚СЊ С‚РµРєСЃС‚РѕРІС‹Р№ С„Р°Р№Р». РџРѕР¶Р°Р»СѓР№СЃС‚Р°, СЃРѕС…СЂР°РЅРёС‚Рµ С„Р°Р№Р» РІ РєРѕРґРёСЂРѕРІРєРµ UTF-8."
                    )
        elif file.filename and file.filename.lower().endswith('.docx'):
            # DOCX file - extract text
            workspace_file.raw_payload_bytes = content
            try:
                from services.document_parser import DocumentParser
                parser = DocumentParser()
                workspace_file.raw_payload_text = parser.extract_text_from_docx(content)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ С„Р°Р№Р» .docx: {str(e)}. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РєРѕРЅРІРµСЂС‚РёСЂСѓР№С‚Рµ С„Р°Р№Р» РІ С‚РµРєСЃС‚РѕРІС‹Р№ С„РѕСЂРјР°С‚ (.txt)."
                )
        else:
            # File without extension or with unknown extension
            # Check if it's a binary file that looks like DOCX
            if b'[Content_Types].xml' in content or b'word/' in content or b'PK' in content[:4]:
                raise HTTPException(
                    status_code=400,
                    detail="РћР±РЅР°СЂСѓР¶РµРЅ С„Р°Р№Р» .docx. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РєРѕРЅРІРµСЂС‚РёСЂСѓР№С‚Рµ РµРіРѕ РІ С‚РµРєСЃС‚РѕРІС‹Р№ С„РѕСЂРјР°С‚ (.txt) РїРµСЂРµРґ Р·Р°РіСЂСѓР·РєРѕР№."
                )
            else:
                # Try to treat as text
                try:
                    workspace_file.raw_payload_text = content.decode('utf-8')
                except UnicodeDecodeError:
                    # Try other encodings
                    for encoding in ['cp1251', 'windows-1251', 'latin1']:
                        try:
                            workspace_file.raw_payload_text = content.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="РќРµРїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ С„РѕСЂРјР°С‚ С„Р°Р№Р»Р°. РџРѕР¶Р°Р»СѓР№СЃС‚Р°, Р·Р°РіСЂСѓР·РёС‚Рµ С‚РµРєСЃС‚РѕРІС‹Р№ С„Р°Р№Р» (.txt) СЃ РїСЂР°РІРєР°РјРё."
                        )
    elif text_content:
        # Plain text
        workspace_file.source_type = "text"
        workspace_file.filename = "manual_input.txt"
        workspace_file.raw_payload_text = text_content
    else:
        raise HTTPException(status_code=400, detail="Either file or text_content must be provided")
    
    session.add(workspace_file)
    
    # Audit log
    await AuditService.log_action(
        session, None, AuditAction.edit_upload,
        entity_type="workspace_file",
        entity_id=workspace_file.id,
        metadata={"filename": workspace_file.filename}
    )
    
    await session.commit()
    await session.refresh(workspace_file)
    
    return workspace_file


@router.get("/workspace/files", response_model=List[WorkspaceFileResponse])
async def list_workspace_files(
    base_document_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session)
):
    """Get all workspace files"""
    query = select(WorkspaceFile).where()
    
    if base_document_id:
        query = query.where(WorkspaceFile.base_document_id == base_document_id)
    
    result = await session.execute(query)
    files = result.scalars().all()
    return files


@router.get("/workspace/file/{file_id}", response_model=WorkspaceFileResponse)
async def get_workspace_file(
    file_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get specific workspace file"""
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == file_id,
            
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return file


@router.delete("/workspace/file/{file_id}")
async def delete_workspace_file(
    file_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Delete workspace file"""
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == file_id,
            
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    await session.delete(file)
    await session.commit()
    
    return {"message": "File deleted successfully"}



