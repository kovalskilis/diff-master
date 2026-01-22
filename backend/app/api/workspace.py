from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from database import get_async_session
from models.document import WorkspaceFile, BaseDocument, AuditAction
import uuid
DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
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
    
    current_user_id = DUMMY_USER_ID
    
    # Verify document exists
    result = await session.execute(
        select(BaseDocument).where(
            BaseDocument.id == base_document_id,
            BaseDocument.user_id == current_user_id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    workspace_file = WorkspaceFile(
        user_id=current_user_id,
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
                        detail="Не удалось декодировать текстовый файл. Пожалуйста, сохраните файл в кодировке UTF-8."
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
                    detail=f"Не удалось обработать файл .docx: {str(e)}. Пожалуйста, конвертируйте файл в текстовый формат (.txt)."
                )
        else:
            # File without extension or with unknown extension
            # Check if it's a binary file that looks like DOCX
            if b'[Content_Types].xml' in content or b'word/' in content or b'PK' in content[:4]:
                raise HTTPException(
                    status_code=400,
                    detail="Обнаружен файл .docx. Пожалуйста, конвертируйте его в текстовый формат (.txt) перед загрузкой."
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
                            detail="Неподдерживаемый формат файла. Пожалуйста, загрузите текстовый файл (.txt) с правками."
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
        session, current_user_id, AuditAction.edit_upload,
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
    
    current_user_id = DUMMY_USER_ID
    
    query = select(WorkspaceFile).where(WorkspaceFile.user_id == current_user_id)
    
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
    
    current_user_id = DUMMY_USER_ID
    
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == file_id,
            WorkspaceFile.user_id == current_user_id
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
    
    current_user_id = DUMMY_USER_ID
    
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == file_id,
            WorkspaceFile.user_id == current_user_id
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    await session.delete(file)
    await session.commit()
    
    return {"message": "File deleted successfully"}

