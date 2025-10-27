from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import sys
from pathlib import Path

# Add app directory to path for imports
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import get_async_session
from auth import current_active_user
from models.user import User
from models.document import WorkspaceFile, EditTarget, EditJobStatus, AuditAction, TaxUnit
from schemas.edit import (

    EditTargetResponse, EditTargetUpdate,
    Phase1Request, Phase1Response,
    Phase2Request, Phase2Response,
    TaskStatusResponse
)
from services.audit_service import AuditService
from worker.tasks import phase1_find_targets, phase2_apply_edits
from celery.result import AsyncResult

router = APIRouter()


@router.post("/edits/apply/phase1", response_model=Phase1Response)
async def start_phase1(
    request: Phase1Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-4 Stage 1: Start "Find Targets" process
    LLM extracts edit instructions and finds matching tax_unit IDs
    """
    # Verify workspace file belongs to user
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == request.workspace_file_id,
            WorkspaceFile.user_id == user.id
        )
    )
    workspace_file = result.scalar_one_or_none()
    if not workspace_file:
        raise HTTPException(status_code=404, detail="Workspace file not found")
    
    # Start Celery task
    task = phase1_find_targets.delay(
        workspace_file_id=request.workspace_file_id,
        user_id=str(user.id)
    )
    
    # Audit log
    await AuditService.log_action(
        session, user.id, AuditAction.phase1_start,
        entity_type="workspace_file",
        entity_id=request.workspace_file_id,
        metadata={"task_id": task.id}
    )
    await session.commit()
    
    return Phase1Response(
        task_id=task.id,
        message="Phase 1 (Find Targets) started"
    )


@router.get("/edits/targets/{workspace_file_id}", response_model=List[EditTargetResponse])
async def get_edit_targets(
    workspace_file_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-4.5: Get list of targets for review stage
    Returns all edit targets with their matched tax units
    """
    # Verify workspace file belongs to user
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == workspace_file_id,
            WorkspaceFile.user_id == user.id
        )
    )
    workspace_file = result.scalar_one_or_none()
    if not workspace_file:
        raise HTTPException(status_code=404, detail="Workspace file not found")
    
    # Get all edit targets with relationships preloaded
    result = await session.execute(
        select(EditTarget)
        .options(
            selectinload(EditTarget.initial_tax_unit),
            selectinload(EditTarget.confirmed_tax_unit)
        )
        .where(
            EditTarget.workspace_file_id == workspace_file_id,
            EditTarget.user_id == user.id
        )
    )
    targets = result.scalars().all()
    
    # Enrich with tax unit info
    response_list = []
    for target in targets:
        response = EditTargetResponse(
            id=target.id,
            workspace_file_id=target.workspace_file_id,
            status=target.status,
            instruction_text=target.instruction_text,
            article_number=target.conflicts_json.get('article') if target.conflicts_json else None,  # Добавить номер статьи
            initial_tax_unit_id=target.initial_tax_unit_id,
            confirmed_tax_unit_id=target.confirmed_tax_unit_id,
            conflicts_json=target.conflicts_json,
            base_document_id=workspace_file.base_document_id  # Добавить base_document_id
        )
        print(f"[API] Returning target {target.id} with base_document_id={workspace_file.base_document_id}")
        
        # Add tax unit details
        if target.initial_tax_unit:
            response.initial_tax_unit_title = target.initial_tax_unit.title
            response.initial_tax_unit_breadcrumbs = target.initial_tax_unit.breadcrumbs_path
        
        if target.confirmed_tax_unit:
            response.confirmed_tax_unit_title = target.confirmed_tax_unit.title
            response.confirmed_tax_unit_breadcrumbs = target.confirmed_tax_unit.breadcrumbs_path
        
        response_list.append(response)
    
    return response_list


@router.put("/edits/target/{target_id}", response_model=EditTargetResponse)
async def update_edit_target(
    target_id: int,
    update: EditTargetUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-4.5: Update target's confirmed_tax_unit_id
    Allows user to manually correct LLM's match
    """
    print(f"[API] Updating target {target_id} with tax_unit_id {update.confirmed_tax_unit_id} for user {user.id}")
    
    result = await session.execute(
        select(EditTarget).where(
            EditTarget.id == target_id,
            EditTarget.user_id == user.id
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        print(f"[API] Target {target_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Edit target not found")
    
    target.confirmed_tax_unit_id = update.confirmed_tax_unit_id
    if update.status:
        target.status = update.status
    
    await session.commit()
    await session.refresh(target)
    print(f"[API] Target {target_id} updated successfully with tax_unit_id {target.confirmed_tax_unit_id}")
    
    # Get workspace file to access base_document_id
    workspace_file_result = await session.execute(
        select(WorkspaceFile).where(WorkspaceFile.id == target.workspace_file_id)
    )
    workspace_file = workspace_file_result.scalar_one_or_none()
    
    # Load confirmed tax unit if it exists
    confirmed_tax_unit_title = None
    confirmed_tax_unit_breadcrumbs = None
    if target.confirmed_tax_unit_id:
        tax_unit_result = await session.execute(
            select(TaxUnit).where(TaxUnit.id == target.confirmed_tax_unit_id)
        )
        confirmed_tax_unit = tax_unit_result.scalar_one_or_none()
        if confirmed_tax_unit:
            confirmed_tax_unit_title = confirmed_tax_unit.title
            confirmed_tax_unit_breadcrumbs = confirmed_tax_unit.breadcrumbs_path
    
    response = EditTargetResponse(
        id=target.id,
        workspace_file_id=target.workspace_file_id,
        status=target.status,
        instruction_text=target.instruction_text,
        article_number=target.conflicts_json.get('article') if target.conflicts_json else None,
        initial_tax_unit_id=target.initial_tax_unit_id,
        confirmed_tax_unit_id=target.confirmed_tax_unit_id,
        conflicts_json=target.conflicts_json,
        base_document_id=workspace_file.base_document_id if workspace_file else None
    )
    
    response.confirmed_tax_unit_title = confirmed_tax_unit_title
    response.confirmed_tax_unit_breadcrumbs = confirmed_tax_unit_breadcrumbs
    
    return response


@router.post("/edits/apply/phase2", response_model=Phase2Response)
async def start_phase2(
    request: Phase2Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-4 Stage 2: Start "Apply Edits" process
    Applies LLM transformations to confirmed targets
    """
    # Verify workspace file belongs to user
    result = await session.execute(
        select(WorkspaceFile).where(
            WorkspaceFile.id == request.workspace_file_id,
            WorkspaceFile.user_id == user.id
        )
    )
    workspace_file = result.scalar_one_or_none()
    if not workspace_file:
        raise HTTPException(status_code=404, detail="Workspace file not found")
    
    # Start Celery task
    task = phase2_apply_edits.delay(
        workspace_file_id=request.workspace_file_id,
        user_id=str(user.id)
    )
    
    # Audit log
    await AuditService.log_action(
        session, user.id, AuditAction.phase2_start,
        entity_type="workspace_file",
        entity_id=request.workspace_file_id,
        metadata={"task_id": task.id}
    )
    await session.commit()
    
    return Phase2Response(
        task_id=task.id,
        message="Phase 2 (Apply Edits) started"
    )


@router.get("/edits/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    user: User = Depends(current_active_user)
):
    """Get status of Celery task"""
    task_result = AsyncResult(task_id)
    
    response = TaskStatusResponse(
        task_id=task_id,
        status=task_result.status
    )
    
    if task_result.ready():
        if task_result.successful():
            response.result = task_result.result
        else:
            response.error = str(task_result.info)
    
    return response

