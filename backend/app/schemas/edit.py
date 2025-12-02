from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from models.document import EditJobStatus


class EditTargetResponse(BaseModel):
    id: int
    workspace_file_id: int
    status: EditJobStatus
    instruction_text: str
    article_number: Optional[str] = None
    article_id: Optional[int] = None
    conflicts_json: Optional[Dict[str, Any]] = None
    
    # Additional fields for UI
    article_title: Optional[str] = None
    base_document_id: Optional[int] = None
    # Whether the referenced article exists in the current document
    article_exists: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)


class EditTargetUpdate(BaseModel):
    article_id: Optional[int] = None
    status: Optional[EditJobStatus] = None


class EditTargetCreate(BaseModel):
    workspace_file_id: int
    instruction_text: str
    article_id: int


class Phase1Request(BaseModel):
    workspace_file_id: int


class Phase1Response(BaseModel):
    task_id: str
    message: str


class Phase2Request(BaseModel):
    workspace_file_id: int
    force_reapply: bool = False


class Phase2Response(BaseModel):
    task_id: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # PENDING, STARTED, SUCCESS, FAILURE
    result: Optional[Any] = None
    error: Optional[str] = None

