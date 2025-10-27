from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import io
from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import uuid

from models.document import (
    Snapshot, TaxUnitVersion, PatchedFragment, TaxUnit
)


class ExportService:
    """
    FR-8, FR-9: Export service for text and Excel reports
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def export_as_text(self, snapshot_id: int) -> str:
        """Export snapshot as plain text"""
        # Get snapshot
        result = await self.session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            return ""
        
        # Get all versions for this snapshot
        result = await self.session.execute(
            select(TaxUnitVersion).where(
                TaxUnitVersion.snapshot_id == snapshot_id
            )
        )
        versions = result.scalars().all()
        
        # Build text
        text_parts = []
        for version in versions:
            tax_unit = version.tax_unit
            text_parts.append(f"\n{'='*80}\n")
            text_parts.append(f"{tax_unit.breadcrumbs_path}\n")
            text_parts.append(f"{tax_unit.title}\n")
            text_parts.append(f"{'-'*80}\n")
            text_parts.append(f"{version.text_content}\n")
        
        return ''.join(text_parts)
    
    async def export_as_docx(self, snapshot_id: int) -> bytes:
        """Export snapshot as DOCX"""
        doc = Document()
        doc.add_heading('Экспорт документа', 0)
        
        # Get all versions for this snapshot
        result = await self.session.execute(
            select(TaxUnitVersion).where(
                TaxUnitVersion.snapshot_id == snapshot_id
            )
        )
        versions = result.scalars().all()
        
        for version in versions:
            tax_unit = version.tax_unit
            
            # Add breadcrumbs
            doc.add_paragraph(tax_unit.breadcrumbs_path, style='Heading 3')
            
            # Add title
            if tax_unit.title:
                doc.add_paragraph(tax_unit.title, style='Heading 4')
            
            # Add content
            doc.add_paragraph(version.text_content)
        
        # Save to bytes
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
    
    async def export_as_excel(
        self, 
        snapshot_id: Optional[int] = None,
        workspace_file_id: Optional[int] = None,
        user_id: Optional[uuid.UUID] = None
    ) -> bytes:
        """
        FR-9: Export changes as Excel report
        Columns:
        - ДЕЙСТВУЮЩАЯ НОРМА НК РФ (Было)
        - НОВАЯ НОРМА (Стало)
        - ИЗМЕНЯЕМАЯ/ВВОДИМАЯ НОРМА (Breadcrumbs)
        - ДАТА ВСТУПЛЕНИЯ В ДЕЙСТВИЕ
        - КОММЕНТАРИИ
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Изменения"
        
        # Header styling
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        
        # Headers
        headers = [
            "№",
            "ИЗМЕНЯЕМАЯ/ВВОДИМАЯ НОРМА",
            "ДЕЙСТВУЮЩАЯ НОРМА НК РФ",
            "НОВАЯ НОРМА",
            "ДАТА ВСТУПЛЕНИЯ В ДЕЙСТВИЕ",
            "КОММЕНТАРИИ"
        ]
        
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        # Column widths
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 40
        ws.column_dimensions['C'].width = 50
        ws.column_dimensions['D'].width = 50
        ws.column_dimensions['E'].width = 20
        ws.column_dimensions['F'].width = 40
        
        # Get patched fragments
        query = select(PatchedFragment)
        if user_id:
            query = query.where(PatchedFragment.user_id == user_id)
        
        result = await self.session.execute(query)
        fragments = result.scalars().all()
        
        # Fill data
        for idx, fragment in enumerate(fragments, start=2):
            tax_unit = fragment.tax_unit
            
            ws.cell(row=idx, column=1, value=idx-1)  # №
            ws.cell(row=idx, column=2, value=tax_unit.breadcrumbs_path or "")  # ИЗМЕНЯЕМАЯ НОРМА
            ws.cell(row=idx, column=3, value=fragment.before_text or "")  # ДЕЙСТВУЮЩАЯ НОРМА
            ws.cell(row=idx, column=4, value=fragment.after_text or "")  # НОВАЯ НОРМА
            ws.cell(row=idx, column=5, value="")  # ДАТА (заполняется вручную)
            ws.cell(row=idx, column=6, value="")  # КОММЕНТАРИИ
            
            # Styling for data rows
            for col in range(1, 7):
                cell = ws.cell(row=idx, column=col)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        
        # Save to bytes
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

