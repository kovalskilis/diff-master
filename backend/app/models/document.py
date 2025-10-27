import sys
from pathlib import Path

# Add app directory to path for imports
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, 
    DateTime, Enum, LargeBinary, UUID, Index
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from models.user import User  # Import User model for foreign key references
import enum
import uuid


class TaxUnitType(str, enum.Enum):
    section = "section"
    chapter = "chapter"
    article = "article"
    clause = "clause"
    sub_clause = "sub_clause"


class EditJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    review = "review"


class ChangeType(str, enum.Enum):
    added = "added"
    modified = "modified"
    deleted = "deleted"


class AuditAction(str, enum.Enum):
    import_ = "import"
    edit_upload = "edit_upload"
    phase1_start = "phase1_start"
    phase2_start = "phase2_start"
    commit = "commit"
    rollback = "rollback"
    export_txt = "export_txt"
    export_excel = "export_excel"
    delete_ = "delete_"


class BaseDocument(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "base_document"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())
    source_type = Column(String(10))  # docx, txt
    structure = Column(JSONB)  # Parsed document structure with articles
    
    # Relationships
    tax_units = relationship("TaxUnit", back_populates="document", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="document", cascade="all, delete-orphan")
    workspace_files = relationship("WorkspaceFile", back_populates="document", cascade="all, delete-orphan")


class Snapshot(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "snapshot"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    base_document_id = Column(Integer, ForeignKey("base_document.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    comment = Column(Text)
    
    # Relationships
    document = relationship("BaseDocument", back_populates="snapshots")
    versions = relationship("TaxUnitVersion", back_populates="snapshot", cascade="all, delete-orphan")
    excel_reports = relationship("ExcelReport", back_populates="snapshot", cascade="all, delete-orphan")


class TaxUnit(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "tax_unit"
    
    id = Column(Integer, primary_key=True, index=True)
    base_document_id = Column(Integer, ForeignKey("base_document.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(TaxUnitType), nullable=False)
    parent_id = Column(Integer, ForeignKey("tax_unit.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(Text)
    breadcrumbs_path = Column(Text)
    current_version_id = Column(Integer, nullable=True)
    fulltext_vector = Column(TSVECTOR)
    
    # Relationships
    document = relationship("BaseDocument", back_populates="tax_units")
    parent = relationship("TaxUnit", remote_side=[id], backref="children")
    versions = relationship("TaxUnitVersion", back_populates="tax_unit", cascade="all, delete-orphan")
    edit_targets_initial = relationship("EditTarget", foreign_keys="EditTarget.initial_tax_unit_id", back_populates="initial_tax_unit")
    edit_targets_confirmed = relationship("EditTarget", foreign_keys="EditTarget.confirmed_tax_unit_id", back_populates="confirmed_tax_unit")
    patched_fragments = relationship("PatchedFragment", back_populates="tax_unit", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_fulltext_vector', 'fulltext_vector', postgresql_using='gin'),
    )


class TaxUnitVersion(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "tax_unit_version"
    
    id = Column(Integer, primary_key=True, index=True)
    tax_unit_id = Column(Integer, ForeignKey("tax_unit.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshot.id", ondelete="CASCADE"), nullable=False, index=True)
    text_content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    
    # Relationships
    tax_unit = relationship("TaxUnit", back_populates="versions")
    snapshot = relationship("Snapshot", back_populates="versions")


class WorkspaceFile(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "workspace_file"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    base_document_id = Column(Integer, ForeignKey("base_document.id"), nullable=True)
    source_type = Column(String(10))  # file, text
    filename = Column(String(255))
    raw_payload_text = Column(Text)
    raw_payload_bytes = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    document = relationship("BaseDocument", back_populates="workspace_files")
    edit_targets = relationship("EditTarget", back_populates="workspace_file", cascade="all, delete-orphan")


class EditTarget(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "edit_target"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_file_id = Column(Integer, ForeignKey("workspace_file.id"), nullable=False, index=True)
    status = Column(Enum(EditJobStatus), default=EditJobStatus.pending, nullable=False)
    instruction_text = Column(Text, nullable=False)
    initial_tax_unit_id = Column(Integer, ForeignKey("tax_unit.id"), nullable=True)
    confirmed_tax_unit_id = Column(Integer, ForeignKey("tax_unit.id"), nullable=True)
    conflicts_json = Column(JSONB)
    
    # Relationships
    workspace_file = relationship("WorkspaceFile", back_populates="edit_targets")
    initial_tax_unit = relationship("TaxUnit", foreign_keys=[initial_tax_unit_id], back_populates="edit_targets_initial")
    confirmed_tax_unit = relationship("TaxUnit", foreign_keys=[confirmed_tax_unit_id], back_populates="edit_targets_confirmed")
    patched_fragments = relationship("PatchedFragment", back_populates="edit_target", cascade="all, delete-orphan")


class PatchedFragment(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "patched_fragment"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    edit_target_id = Column(Integer, ForeignKey("edit_target.id"), nullable=False, index=True)
    tax_unit_id = Column(Integer, ForeignKey("tax_unit.id"), nullable=False, index=True)
    before_text = Column(Text)
    after_text = Column(Text)
    change_type = Column(Enum(ChangeType), nullable=False)
    metadata_json = Column(JSONB)
    
    # Relationships
    edit_target = relationship("EditTarget", back_populates="patched_fragments")
    tax_unit = relationship("TaxUnit", back_populates="patched_fragments")


class ExcelReport(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "excel_report"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshot.id"), nullable=True)
    file_path = Column(String(512))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    snapshot = relationship("Snapshot", back_populates="excel_reports")


class AuditLog(Base):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(Enum(AuditAction), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    metadata_json = Column("metadata", JSONB)  # Renamed to avoid conflict with SQLAlchemy's metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

