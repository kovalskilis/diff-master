from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from models.document import EditJobStatus


class EditTargetResponse(BaseModel):
    id: int
    workspace_file_id: int
    status: EditJobStatus
    instruction_text: str
    article_number: Optional[str] = None  # Добавить поле для номера статьи
    initial_tax_unit_id: Optional[int] = None
    confirmed_tax_unit_id: Optional[int] = None
    conflicts_json: Optional[Dict[str, Any]] = None
    
    # Additional fields for UI
    initial_tax_unit_title: Optional[str] = None
    initial_tax_unit_breadcrumbs: Optional[str] = None
    confirmed_tax_unit_title: Optional[str] = None
    confirmed_tax_unit_breadcrumbs: Optional[str] = None
    base_document_id: Optional[int] = None  # Для поиска
    
    model_config = ConfigDict(from_attributes=True)


class EditTargetUpdate(BaseModel):
    confirmed_tax_unit_id: int
    status: Optional[EditJobStatus] = None


class Phase1Request(BaseModel):
    workspace_file_id: int


class Phase1Response(BaseModel):
    task_id: str
    message: str


class Phase2Request(BaseModel):
    workspace_file_id: int


class Phase2Response(BaseModel):
    task_id: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # PENDING, STARTED, SUCCESS, FAILURE
    result: Optional[Any] = None
    error: Optional[str] = None

