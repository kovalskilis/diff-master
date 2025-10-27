from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import io

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import PatchedFragment, Snapshot, ExcelReport, AuditAction
from services.export_service import ExportService
from services.audit_service import AuditService


import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

router = APIRouter()


@router.post("/export/text")
async def export_text(
    snapshot_id: int,
    format: str = "txt",  # txt or docx
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-8: Export texts in .txt or .docx format
    """
    # Verify snapshot belongs to user
    result = await session.execute(
        select(Snapshot).where(
            Snapshot.id == snapshot_id,
            Snapshot.user_id == user.id
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    if format not in ["txt", "docx"]:
        raise HTTPException(status_code=400, detail="Format must be 'txt' or 'docx'")
    
    export_service = ExportService(session)
    
    if format == "txt":
        content = await export_service.export_as_text(snapshot_id)
        
        # Audit log
        await AuditService.log_action(
            session, user.id, AuditAction.export_txt,
            entity_type="snapshot",
            entity_id=snapshot_id,
            metadata={"format": "txt"}
        )
        await session.commit()
        
        return Response(
            content=content.encode('utf-8'),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=export_{snapshot_id}.txt"
            }
        )
    else:  # docx
        docx_bytes = await export_service.export_as_docx(snapshot_id)
        
        # Audit log
        await AuditService.log_action(
            session, user.id, AuditAction.export_txt,
            entity_type="snapshot",
            entity_id=snapshot_id,
            metadata={"format": "docx"}
        )
        await session.commit()
        
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=export_{snapshot_id}.docx"
            }
        )


@router.post("/export/excel")
async def export_excel(
    snapshot_id: Optional[int] = None,
    workspace_file_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-9: Generate Excel report with changes
    Columns: ДЕЙСТВУЮЩАЯ НОРМА НК РФ, НОВАЯ НОРМА, ИЗМЕНЯЕМАЯ/ВВОДИМАЯ НОРМА, ДАТА ВСТУПЛЕНИЯ, КОММЕНТАРИИ
    """
    if not snapshot_id and not workspace_file_id:
        raise HTTPException(
            status_code=400,
            detail="Either snapshot_id or workspace_file_id must be provided"
        )
    
    export_service = ExportService(session)
    
    # Generate Excel file
    excel_bytes = await export_service.export_as_excel(
        snapshot_id=snapshot_id,
        workspace_file_id=workspace_file_id,
        user_id=user.id
    )
    
    # Save report record
    excel_report = ExcelReport(
        user_id=user.id,
        snapshot_id=snapshot_id,
        file_path=f"report_{snapshot_id or workspace_file_id}.xlsx"
    )
    session.add(excel_report)
    
    # Audit log
    await AuditService.log_action(
        session, user.id, AuditAction.export_excel,
        entity_type="snapshot" if snapshot_id else "workspace_file",
        entity_id=snapshot_id or workspace_file_id,
        metadata={"report_id": excel_report.id}
    )
    await session.commit()
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=changes_report_{snapshot_id or workspace_file_id}.xlsx"
        }
    )

