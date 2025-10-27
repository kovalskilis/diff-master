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
from models.document import WorkspaceFile, EditTarget, EditJobStatus, AuditAction, Article, PatchedFragment
from schemas.edit import (
    EditTargetResponse, EditTargetUpdate, EditTargetCreate,
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
    # Flush session to ensure we get latest data
    await session.flush()
    
    result = await session.execute(
        select(EditTarget)
        .options(
            selectinload(EditTarget.article)
        )
        .where(
            EditTarget.workspace_file_id == workspace_file_id,
            EditTarget.user_id == user.id
        )
    )
    targets = result.scalars().all()
    
    # Enrich with article info
    response_list = []
    for target in targets:
        article_number = target.conflicts_json.get('article') if target.conflicts_json else None
        
        # Get article details if exists
        article_title = None
        if target.article:
            article_title = target.article.title
        
        response = EditTargetResponse(
            id=target.id,
            workspace_file_id=target.workspace_file_id,
            status=target.status,
            instruction_text=target.instruction_text,
            article_number=article_number,
            article_id=target.article_id,
            conflicts_json=target.conflicts_json,
            base_document_id=workspace_file.base_document_id,
            article_title=article_title
        )
        print(f"[API] Returning target {target.id} with article_id={target.article_id}")
        
        response_list.append(response)
    
    return response_list


@router.post("/edits/target", response_model=EditTargetResponse)
async def create_edit_target(
    create: EditTargetCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    Create a new edit target
    """
    print(f"[API] Creating target for workspace_file {create.workspace_file_id}, article_id {create.article_id}")
    
    # Get article details
    article_result = await session.execute(
        select(Article).where(Article.id == create.article_id)
    )
    article = article_result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Create new target
    new_target = EditTarget(
        user_id=user.id,
        workspace_file_id=create.workspace_file_id,
        status=EditJobStatus.pending,
        instruction_text=create.instruction_text,
        article_id=create.article_id,
        conflicts_json={
            "article": article.article_number,
            "source": "manual",
            "content_length": len(create.instruction_text),
            "structured_format": True,
            "auto_confirmed": True
        }
    )
    session.add(new_target)
    await session.commit()
    await session.refresh(new_target)
    
    print(f"[API] Target {new_target.id} created successfully")
    
    response = EditTargetResponse(
        id=new_target.id,
        workspace_file_id=new_target.workspace_file_id,
        status=new_target.status,
        instruction_text=new_target.instruction_text,
        article_number=article.article_number,
        article_id=new_target.article_id,
        conflicts_json=new_target.conflicts_json,
        base_document_id=article.base_document_id,
        article_title=article.title
    )
    
    return response


@router.put("/edits/target/{target_id}", response_model=EditTargetResponse)
async def update_edit_target(
    target_id: int,
    update: EditTargetUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    FR-4.5: Update target's article_id
    Allows user to manually correct LLM's match
    """
    print(f"[API] Updating target {target_id} with article_id {update.article_id} for user {user.id}")
    
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
    
    # Update article_id if provided
    if update.article_id is not None:
        target.article_id = update.article_id
    
    if update.status:
        target.status = update.status
    
    await session.commit()
    await session.refresh(target)
    print(f"[API] Target {target_id} updated successfully with article_id {target.article_id}")
    
    # Get workspace file and article details
    workspace_file_result = await session.execute(
        select(WorkspaceFile).where(WorkspaceFile.id == target.workspace_file_id)
    )
    workspace_file = workspace_file_result.scalar_one_or_none()
    
    # Load article if it exists
    article_title = None
    article_number = None
    if target.article_id:
        article_result = await session.execute(
            select(Article).where(Article.id == target.article_id)
        )
        article = article_result.scalar_one_or_none()
        if article:
            article_title = article.title
            article_number = article.article_number
    
    response = EditTargetResponse(
        id=target.id,
        workspace_file_id=target.workspace_file_id,
        status=target.status,
        instruction_text=target.instruction_text,
        article_number=article_number,
        article_id=target.article_id,
        conflicts_json=target.conflicts_json,
        base_document_id=workspace_file.base_document_id if workspace_file else None,
        article_title=article_title
    )
    
    return response


@router.delete("/edits/target/{target_id}")
async def delete_edit_target(
    target_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """
    Delete an edit target
    """
    print(f"[API] Deleting target {target_id} for user {user.id}")
    
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
    
    await session.delete(target)
    await session.commit()
    print(f"[API] Target {target_id} deleted successfully")
    
    return {"message": "Edit target deleted successfully"}


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
    
    # Check if fragments already exist and if any edits have been changed
    # Get all targets for this workspace
    targets_result = await session.execute(
        select(EditTarget).where(
            EditTarget.workspace_file_id == request.workspace_file_id,
            EditTarget.user_id == user.id,
            EditTarget.article_id.isnot(None)
        )
    )
    targets = targets_result.scalars().all()
    
    # Check if fragments already exist for these targets
    has_existing_fragments = False
    if targets:
        target_ids = [t.id for t in targets]
        fragments_result = await session.execute(
            select(PatchedFragment).where(
                PatchedFragment.edit_target_id.in_(target_ids)
            )
        )
        existing_fragments = fragments_result.scalars().all()
        has_existing_fragments = len(existing_fragments) > 0
    
    # Only start task if:
    # 1. No fragments exist yet (first run), OR
    # 2. User explicitly requests re-application
    if has_existing_fragments and not request.force_reapply:
        return Phase2Response(
            task_id="",
            message="Edits already applied. Use force_reapply=true to re-apply."
        )
    
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
        metadata={"task_id": task.id, "force_reapply": request.force_reapply}
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

