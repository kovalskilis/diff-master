from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime
from models.document import TaxUnitType, ChangeType


class BaseDocumentCreate(BaseModel):
    name: str
    source_type: str


class BaseDocumentResponse(BaseModel):
    id: int
    name: str
    source_type: str
    imported_at: datetime
    structure: Optional[Dict[str, Dict[str, str]]] = None
    
    model_config = ConfigDict(from_attributes=True)


class TaxUnitResponse(BaseModel):
    id: int
    type: TaxUnitType
    title: Optional[str] = None
    breadcrumbs_path: Optional[str] = None
    parent_id: Optional[int] = None
    current_text: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ArticleResponse(BaseModel):
    id: int
    article_number: str
    title: Optional[str] = None
    content: str
    
    model_config = ConfigDict(from_attributes=True)


class TaxUnitHierarchyResponse(BaseModel):
    id: int
    type: TaxUnitType
    title: Optional[str] = None
    breadcrumbs_path: Optional[str] = None
    children: List['TaxUnitHierarchyResponse'] = []
    
    model_config = ConfigDict(from_attributes=True)


class SnapshotResponse(BaseModel):
    id: int
    base_document_id: int
    created_at: datetime
    comment: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class WorkspaceFileCreate(BaseModel):
    base_document_id: int
    filename: Optional[str] = None
    raw_payload_text: Optional[str] = None


class WorkspaceFileResponse(BaseModel):
    id: int
    base_document_id: Optional[int] = None
    source_type: str
    filename: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SearchResult(BaseModel):
    article_id: int
    title: Optional[str] = None
    article_number: Optional[str] = None
    text_snippet: str
    rank: float
    
    model_config = ConfigDict(from_attributes=True)


class DiffResponse(BaseModel):
    article_id: Optional[int] = None
    title: Optional[str] = None
    article_number: Optional[str] = None
    before_text: str
    after_text: str
    change_type: ChangeType
    diff_html: Optional[str] = None

