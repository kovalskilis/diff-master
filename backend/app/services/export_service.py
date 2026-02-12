from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict, Tuple
import io
import difflib
from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import uuid
import re

from models.document import (
    Snapshot, ArticleVersion, PatchedFragment, Article, EditTarget
)
from services.llm_service import LLMService

# Try importing rich text support (openpyxl >= 3.1)
try:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    HAS_RICH_TEXT = True
except ImportError:
    HAS_RICH_TEXT = False


def extract_change_blocks(before_text: str, after_text: str) -> List[Dict]:
    """
    Compare before and after text line-by-line, extract only changed blocks.
    Each block = {'before': str, 'after': str, 'type': 'replace'|'insert'|'delete'}
    """
    before_lines = (before_text or "").splitlines()
    after_lines = (after_text or "").splitlines()
    
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        
        before_block = '\n'.join(before_lines[i1:i2]).strip()
        after_block = '\n'.join(after_lines[j1:j2]).strip()
        
        # Skip empty changes
        if not before_block and not after_block:
            continue
        
        changes.append({
            'before': before_block,
            'after': after_block,
            'type': tag  # 'replace', 'insert', 'delete'
        })
    
    return changes


def build_rich_after_text(before_block: str, after_block: str, change_type: str):
    """
    Build rich text for the 'after' column with bold on changed/added words.
    Returns CellRichText if available, otherwise plain string.
    """
    if not HAS_RICH_TEXT:
        return after_block
    
    try:
        bold_font = InlineFont(b=True)
        
        # Pure insertion — all text is bold
        if change_type == 'insert' or not before_block.strip():
            return CellRichText(TextBlock(bold_font, after_block))
        
        # Replace — find changed words and bold them
        before_words = before_block.split()
        after_words = after_block.split()
        
        matcher = difflib.SequenceMatcher(None, before_words, after_words)
        
        parts = []
        first = True
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            chunk = ' '.join(after_words[j1:j2])
            if not chunk:
                continue
            
            # Add space between chunks (except first)
            prefix = '' if first else ' '
            first = False
            
            if tag == 'equal':
                parts.append(prefix + chunk)
            else:
                parts.append(TextBlock(bold_font, prefix + chunk))
        
        if parts:
            return CellRichText(*parts)
        return after_block
    except Exception as e:
        print(f"[RichText] Fallback to plain text: {e}")
        return after_block


def extract_effective_date_heuristic(before_text: str, after_text: str, instruction: Optional[str]) -> Optional[str]:
    """
    Extract effective date using heuristics (no LLM).
    Searches for dates near 'вступ' keyword.
    """
    context_sources = [after_text or "", instruction or "", before_text or ""]
    
    # 1) dd.mm.yyyy near 'вступ'
    for src in context_sources:
        for m in re.finditer(r'вступ\w{0,12}[^\.]{0,140}?(\d{1,2}\.\d{1,2}\.\d{4})', src, flags=re.IGNORECASE | re.DOTALL):
            return m.group(1)
    
    # 2) Textual russian date: "с 1 января 2026 года"
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
    
    # 3) General date pattern: "по истечении одного месяца со дня официального опубликования"
    for src in context_sources:
        m = re.search(r'по истечении[^\.]{0,100}опубликования', src, flags=re.IGNORECASE)
        if m:
            return "вступает в силу по истечении одного месяца со дня официального опубликования настоящего Федерального закона"
    
    return None


def detect_banking_heuristic(*texts: Optional[str]) -> bool:
    """Simple keyword-based detector for banking-related changes."""
    combined = " ".join([t or "" for t in texts]).lower()
    if not combined.strip():
        return False
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


def build_article_reference(article_number: Optional[str], instruction: Optional[str]) -> str:
    """
    Build a detailed article reference like 'п. 7 ст. 6.1 НК РФ'
    from the instruction text.
    """
    if not article_number:
        return ""
    
    base_ref = f"ст. {article_number} НК РФ"
    
    if instruction:
        # Try to extract specific paragraph/sub-paragraph references
        # e.g. "Пункт 7, подпункт 5:" -> "п. 7 пп. 5 ст. 6.1 НК РФ"
        parts = []
        
        # Look for "Пункт X" or "пункте X"
        punkt_match = re.search(r'[Пп]ункт[еа]?\s+(\d+[\.\d]*)', instruction)
        if punkt_match:
            parts.append(f"п. {punkt_match.group(1)}")
        
        # Look for "подпункт X" or "подпункте X"
        podpunkt_match = re.search(r'[Пп]одпункт[еа]?\s+(\d+[\.\d]*)', instruction)
        if podpunkt_match:
            parts.append(f"пп. {podpunkt_match.group(1)}")
        
        # Look for "абзац X"
        abzac_match = re.search(r'[Аа]бзац[еа]?\s+(\w+)', instruction)
        if abzac_match:
            parts.append(f"абз. {abzac_match.group(1)}")
        
        if parts:
            return f"{' '.join(parts)} {base_ref}"
    
    return base_ref


class ExportService:
    """
    FR-8, FR-9: Export service for text and Excel reports
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def export_as_text(self, snapshot_id: int) -> str:
        """Export snapshot as plain text"""
        result = await self.session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            return ""
        
        result = await self.session.execute(
            select(ArticleVersion).where(
                ArticleVersion.snapshot_id == snapshot_id
            )
        )
        versions = result.scalars().all()
        
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
        
        result = await self.session.execute(
            select(ArticleVersion).where(
                ArticleVersion.snapshot_id == snapshot_id
            )
        )
        versions = result.scalars().all()
        
        for version in versions:
            article = version.article
            article_title = f"Статья {article.article_number}" if article and article.article_number else "Статья"
            doc.add_paragraph(article_title, style='Heading 3')
            if article and article.title:
                doc.add_paragraph(article.title, style='Heading 4')
            doc.add_paragraph(version.content)
        
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
        FR-9: Export changes as Excel report matching the legal document format.
        
        Columns:
        1. ДЕЙСТВУЮЩАЯ НОРМА НК РФ — only changed paragraphs (before)
        2. НОВАЯ НОРМА — only changed paragraphs (after), with bold on changes
        3. ИЗМЕНЯЕМАЯ/ВВОДИМАЯ НОРМА И ДАТА ВСТУПЛЕНИЯ В ДЕЙСТВИЕ
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Изменения"
        
        # ── Styles ──
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11, name="Times New Roman")
        data_font = Font(size=10, name="Times New Roman")
        chapter_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
        chapter_font = Font(bold=True, size=10, name="Times New Roman")
        italic_font = Font(italic=True, size=10, name="Times New Roman", color="888888")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # ── Headers (row 1) ──
        headers = [
            "ДЕЙСТВУЮЩАЯ НОРМА НК РФ",
            "НОВАЯ НОРМА",
            "ИЗМЕНЯЕМАЯ/ ВВОДИМАЯ\nНОРМА\nИ\nДАТА ВСТУПЛЕНИЯ В\nДЕЙСТВИЕ",
            "КОММЕНТАРИИ",
            "БАНКОВСКИЙ\nСЕГМЕНТ"
        ]
        
        num_cols = len(headers)
        
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        
        # Column widths
        ws.column_dimensions['A'].width = 55
        ws.column_dimensions['B'].width = 55
        ws.column_dimensions['C'].width = 30
        ws.column_dimensions['D'].width = 45
        ws.column_dimensions['E'].width = 18
        
        # Row height for header
        ws.row_dimensions[1].height = 60
        
        # ── Get patched fragments ──
        query = select(PatchedFragment)
        
        if workspace_file_id:
            target_ids_result = await self.session.execute(
                select(EditTarget.id).where(
                    EditTarget.workspace_file_id == workspace_file_id
                )
            )
            target_ids = [row[0] for row in target_ids_result]
            if target_ids:
                query = query.where(PatchedFragment.edit_target_id.in_(target_ids))
            else:
                buffer = io.BytesIO()
                wb.save(buffer)
                buffer.seek(0)
                return buffer.getvalue()
        
        result = await self.session.execute(query)
        fragments = result.scalars().all()
        
        # ── Sort fragments by article number ──
        async def get_article_for_fragment(frag):
            if frag.article_id:
                r = await self.session.execute(
                    select(Article).where(Article.id == frag.article_id)
                )
                return r.scalar_one_or_none()
            return None
        
        # Preload articles
        fragment_articles = {}
        for frag in fragments:
            article = await get_article_for_fragment(frag)
            fragment_articles[frag.id] = article
        
        # Sort by article number (numeric sort)
        def sort_key(frag):
            art = fragment_articles.get(frag.id)
            if art and art.article_number:
                try:
                    # Handle "6.1" -> (6, 1), "11" -> (11, 0)
                    parts = art.article_number.split('.')
                    return tuple(int(p) for p in parts)
                except ValueError:
                    return (999, 0)
            return (999, 0)
        
        fragments = sorted(fragments, key=sort_key)
        
        # ── Chapter header row ──
        current_row = 2
        
        # Initialize LLM service for comments
        llm_service = LLMService()
        
        # Add "1 Часть НК РФ" header
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_cols)
        cell = ws.cell(row=current_row, column=1, value="1 Часть НК РФ")
        cell.fill = chapter_fill
        cell.font = chapter_font
        cell.alignment = Alignment(horizontal="left", vertical="center")
        for col in range(1, num_cols + 1):
            ws.cell(row=current_row, column=col).border = thin_border
        current_row += 1
        
        # ── Fill data rows ──
        for frag_idx, fragment in enumerate(fragments):
            article = fragment_articles.get(fragment.id)
            
            # Get instruction text
            instruction = None
            try:
                if fragment.metadata_json and isinstance(fragment.metadata_json, dict):
                    instruction = fragment.metadata_json.get("instruction")
            except Exception:
                instruction = None
            
            # Extract only changed blocks (not full article)
            change_blocks = extract_change_blocks(
                fragment.before_text or "",
                fragment.after_text or ""
            )
            
            if not change_blocks:
                # No changes detected - skip or show as-is
                continue
            
            # Build article reference
            article_ref = build_article_reference(
                article.article_number if article else None,
                instruction
            )
            
            # Extract effective date
            effective_date = extract_effective_date_heuristic(
                fragment.before_text or "",
                fragment.after_text or "",
                instruction
            )
            
            # Combine reference + date for column 3
            col3_parts = []
            if article_ref:
                col3_parts.append(article_ref)
            if effective_date:
                col3_parts.append("")  # empty line separator
                col3_parts.append(effective_date)
            col3_text = "\n".join(col3_parts)
            
            # ── Build cell content from change blocks ──
            before_parts = []
            after_parts = []
            after_rich_parts = []
            
            for block in change_blocks:
                if block['type'] == 'delete':
                    # Text was deleted
                    before_parts.append(block['before'])
                    after_parts.append("")  # Will show "Норма отсутствует" or empty
                elif block['type'] == 'insert':
                    # New text added
                    before_parts.append("Норма отсутствует")
                    after_parts.append(block['after'])
                else:  # replace
                    before_parts.append(block['before'])
                    after_parts.append(block['after'])
            
            # Join blocks with double newline separator
            before_cell_text = "\n\n".join(p for p in before_parts if p)
            after_cell_text = "\n\n".join(p for p in after_parts if p)
            
            # ── Write row ──
            # Column 1: ДЕЙСТВУЮЩАЯ НОРМА
            cell_before = ws.cell(row=current_row, column=1)
            if not before_cell_text or before_cell_text == "Норма отсутствует":
                cell_before.value = "Норма отсутствует"
                cell_before.font = italic_font
            else:
                cell_before.value = before_cell_text
                cell_before.font = data_font
            cell_before.alignment = Alignment(vertical="top", wrap_text=True)
            cell_before.border = thin_border
            
            # Column 2: НОВАЯ НОРМА (with bold on changes)
            cell_after = ws.cell(row=current_row, column=2)
            
            # Try to build rich text with bold highlighting
            if HAS_RICH_TEXT and len(change_blocks) == 1:
                # Single block - use word-level bold
                block = change_blocks[0]
                rich_value = build_rich_after_text(
                    block['before'], block['after'], block['type']
                )
                cell_after.value = rich_value
            elif HAS_RICH_TEXT and len(change_blocks) > 1:
                # Multiple blocks - build combined rich text
                try:
                    bold_font_inline = InlineFont(b=True)
                    parts = []
                    for i, block in enumerate(change_blocks):
                        if i > 0:
                            parts.append("\n\n")
                        
                        if block['type'] == 'insert':
                            # All bold for new text
                            parts.append(TextBlock(bold_font_inline, block['after']))
                        elif block['type'] == 'delete':
                            continue
                        else:
                            # Word-level comparison
                            bw = block['before'].split()
                            aw = block['after'].split()
                            sm = difflib.SequenceMatcher(None, bw, aw)
                            first_word = True
                            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                                chunk = ' '.join(aw[j1:j2])
                                if not chunk:
                                    continue
                                prefix = '' if first_word else ' '
                                first_word = False
                                if tag == 'equal':
                                    parts.append(prefix + chunk)
                                else:
                                    parts.append(TextBlock(bold_font_inline, prefix + chunk))
                    
                    cell_after.value = CellRichText(*parts) if parts else after_cell_text
                except Exception as e:
                    print(f"[RichText] Multi-block fallback: {e}")
                    cell_after.value = after_cell_text
            else:
                cell_after.value = after_cell_text
            
            cell_after.font = data_font
            cell_after.alignment = Alignment(vertical="top", wrap_text=True)
            cell_after.border = thin_border
            
            # Column 3: ИЗМЕНЯЕМАЯ НОРМА + ДАТА
            cell_ref = ws.cell(row=current_row, column=3, value=col3_text)
            cell_ref.font = data_font
            cell_ref.alignment = Alignment(vertical="top", wrap_text=True)
            cell_ref.border = thin_border
            
            # Column 4: КОММЕНТАРИИ (LLM summary)
            comment_text = ""
            try:
                comment_text = await llm_service.summarize_edit(
                    before_text=before_cell_text,
                    after_text=after_cell_text,
                    article_number=article.article_number if article else None,
                    instruction=instruction
                )
            except Exception:
                if instruction:
                    comment_text = f"Кратко: {instruction[:200]}"
                else:
                    comment_text = "Изменение текста статьи"
            
            cell_comment = ws.cell(row=current_row, column=4, value=comment_text)
            cell_comment.font = data_font
            cell_comment.alignment = Alignment(vertical="top", wrap_text=True)
            cell_comment.border = thin_border
            
            # Column 5: БАНКОВСКИЙ СЕГМЕНТ (heuristic)
            is_banking = detect_banking_heuristic(
                instruction, fragment.before_text, fragment.after_text
            )
            cell_banking = ws.cell(row=current_row, column=5, value="Да" if is_banking else "Нет")
            cell_banking.font = data_font
            cell_banking.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
            cell_banking.border = thin_border
            
            # Auto row height (estimate based on content length)
            max_len = max(len(before_cell_text), len(after_cell_text), 1)
            estimated_lines = max_len // 60 + before_cell_text.count('\n') + 2
            ws.row_dimensions[current_row].height = max(30, min(estimated_lines * 15, 400))
            
            print(f"[Export] Row {current_row}: art={article.article_number if article else '—'}, "
                  f"blocks={len(change_blocks)}, before_len={len(before_cell_text)}, after_len={len(after_cell_text)}")
            
            current_row += 1
        
        # ── Freeze header row ──
        ws.freeze_panes = "A2"
        
        # ── Print area ──
        ws.print_area = f"A1:E{current_row - 1}"
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        
        # Save
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
