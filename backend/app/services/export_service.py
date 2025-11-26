from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import io
from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import uuid
import asyncio
import re

from models.document import (
    Snapshot, ArticleVersion, PatchedFragment, TaxUnit, Article
)
from services.llm_service import LLMService


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
            select(ArticleVersion).where(
                ArticleVersion.snapshot_id == snapshot_id
            )
        )
        versions = result.scalars().all()
        
        # Build text
        text_parts = []
        for version in versions:
            article = version.article
            article_title = f"Статья {article.article_number}" if article else "Статья"
            text_parts.append(f"\n{'='*80}\n")
            text_parts.append(f"{article_title}\n")
            if article and article.title:
                text_parts.append(f"{article.title}\n")
            text_parts.append(f"{'-'*80}\n")
            text_parts.append(f"{version.content}\n")
        
        return ''.join(text_parts)
    
    async def export_as_docx(self, snapshot_id: int) -> bytes:
        """Export snapshot as DOCX"""
        doc = Document()
        doc.add_heading('Экспорт документа', 0)
        
        # Get all versions for this snapshot
        result = await self.session.execute(
            select(ArticleVersion).where(
                ArticleVersion.snapshot_id == snapshot_id
            )
        )
        versions = result.scalars().all()
        
        for version in versions:
            article = version.article
            
            # Add article number
            article_title = f"Статья {article.article_number}" if article and article.article_number else "Статья"
            doc.add_paragraph(article_title, style='Heading 3')
            
            # Add title
            if article and article.title:
                doc.add_paragraph(article.title, style='Heading 4')
            
            # Add content
            doc.add_paragraph(version.content)
        
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
            "КОММЕНТАРИИ",
            "БАНКОВСКИЙ СЕГМЕНТ"
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
        ws.column_dimensions['G'].width = 20
        
        # Get patched fragments
        query = select(PatchedFragment)
        if user_id:
            query = query.where(PatchedFragment.user_id == user_id)
        
        result = await self.session.execute(query)
        fragments = result.scalars().all()
        
        # Initialize LLM service for summaries
        llm_service = LLMService()
        
        def extract_effective_date_local(before_text: str, after_text: str, instruction: Optional[str]) -> Optional[str]:
            """
            Heuristic extractor:
            1) ищем дату формата ДД.ММ.ГГГГ рядом с словами 'вступ' в after_text/instruction
            2) ищем русские даты вида 'с 1 января 2026 года'
            3) если не нашли — просим LLM (fallback)
            """
            context_sources = [after_text or "", instruction or "", before_text or ""]
            
            # 1) dd.mm.yyyy near 'вступ'
            for src in context_sources:
                for m in re.finditer(r'вступ\w{0,12}[^\.]{0,140}?(\d{1,2}\.\d{1,2}\.\d{4})', src, flags=re.IGNORECASE | re.DOTALL):
                    return m.group(1)
            
            # 2) textual russian date: "с 1 января 2026 года"
            month_map = {
                "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
                "мая": "05", "июня": "06", "июля": "07", "августа": "08",
                "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12",
            }
            textual_pattern = re.compile(
                r'вступ\w{0,12}[^\.]{0,140}?с\s+(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})',
                flags=re.IGNORECASE
            )
            for src in context_sources:
                t = textual_pattern.search(src)
                if t:
                    day = int(t.group(1))
                    month = month_map[t.group(2).lower()]
                    year = t.group(3)
                    return f"{day:02d}.{month}.{year}"
            
            return None
        
        def detect_banking_local(*texts: Optional[str]) -> Optional[bool]:
            """
            Simple keyword-based detector for banking-related changes.
            Returns True/False, or None if text is empty.
            """
            combined = " ".join([t or "" for t in texts]).lower()
            if not combined.strip():
                return None
            keywords = [
                "банк россии", "центральный банк", "цб рф", "цбр",
                "банк", "банковск", "кредитн", "расчетный счет",
                "корреспондентский счет", "вклад", "депозит",
                "банковская гаранти", "кредитная организация",
                "платежная система", "платежный агент", "ипотек"
            ]
            for kw in keywords:
                if kw in combined:
                    return True
            return False
        
        # Fill data
        for idx, fragment in enumerate(fragments, start=2):
            # Get article instead of tax_unit
            if fragment.article_id:
                article_result = await self.session.execute(
                    select(Article).where(Article.id == fragment.article_id)
                )
                article = article_result.scalar_one_or_none()
            else:
                article = None
            
            # Use article number or fallback
            breadcrumbs = f"Статья {article.article_number}" if article and article.article_number else ""
            
            ws.cell(row=idx, column=1, value=idx-1)  # №
            ws.cell(row=idx, column=2, value=breadcrumbs)  # ИЗМЕНЯЕМАЯ НОРМА
            ws.cell(row=idx, column=3, value=fragment.before_text or "")  # ДЕЙСТВУЮЩАЯ НОРМА
            ws.cell(row=idx, column=4, value=fragment.after_text or "")  # НОВАЯ НОРМА
            
            # Prepare instruction text for LLM/heuristics
            instruction = None
            try:
                if fragment.metadata_json and isinstance(fragment.metadata_json, dict):
                    instruction = fragment.metadata_json.get("instruction")
            except Exception:
                instruction = None
            
            # Single LLM analysis for date + banking flag
            banking_flag = None
            effective_date = None
            try:
                analysis = await llm_service.analyze_change_metadata(
                    before_text=fragment.before_text or "",
                    after_text=fragment.after_text or "",
                    instruction=instruction,
                    article_number=article.article_number if article else None
                )
                if analysis:
                    effective_date = analysis.get("effective_date") or None
                    banking_flag = analysis.get("is_banking")
                    try:
                        print(f"[ExportMeta] Row {idx-1}: effective_date={effective_date}, is_banking={banking_flag}")
                    except Exception:
                        pass
            except Exception:
                pass
            
            # Heuristic fallback for banking flag if LLM didn't return it
            if banking_flag is None:
                banking_flag = detect_banking_local(instruction, fragment.after_text, fragment.before_text)
                try:
                    print(f"[ExportMeta] Row {idx-1}: banking_heuristic={banking_flag}")
                except Exception:
                    pass
            
            # Heuristic fallback for date if LLM didn't return it
            if not effective_date:
                effective_date = extract_effective_date_local(
                fragment.before_text or "",
                fragment.after_text or "",
                instruction
            )
            if not effective_date:
                try:
                    # Fallback to LLM if heuristics failed
                    combined = f"{instruction or ''}\n\n{fragment.after_text or ''}"
                    effective_date = await llm_service.extract_effective_date(combined)
                except Exception:
                    effective_date = None
            
            # Debug log
            try:
                print(f"[ExportDate] Row {idx-1}: article={article.article_number if article else '—'}, effective_date={effective_date}")
            except Exception:
                pass
            
            ws.cell(row=idx, column=5, value=effective_date or "")  # ДАТА ВСТУПЛЕНИЯ В ДЕЙСТВИЕ
            
            comment_text = ""
            try:
                # Debug logs for diagnostics
                try:
                    print(f"[ExportSummary] Row {idx-1}: article={article.article_number if article else '—'}")
                    print(f"[ExportSummary] BEFORE_LEN={len(fragment.before_text or '')}, AFTER_LEN={len(fragment.after_text or '')}")
                    if instruction:
                        print(f"[ExportSummary] INSTR_LEN={len(instruction)}")
                except Exception:
                    pass
                
                comment_text = await llm_service.summarize_edit(
                    before_text=fragment.before_text or "",
                    after_text=fragment.after_text or "",
                    article_number=article.article_number if article else None,
                    instruction=instruction
                )
            except Exception:
                # Safe fallback
                if instruction:
                    comment_text = f"Кратко: {instruction[:200]}"
                else:
                    comment_text = "Изменение текста статьи; подробности указаны в колонках."
            
            ws.cell(row=idx, column=6, value=comment_text)  # КОММЕНТАРИИ
            # Default to "Нет" if не удалось определить
            ws.cell(row=idx, column=7, value=("Да" if banking_flag is True else "Нет"))  # БАНКОВСКИЙ СЕГМЕНТ
            # Styling for data rows
            for col in range(1, 8):
                cell = ws.cell(row=idx, column=col)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        
        # Save to bytes
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

