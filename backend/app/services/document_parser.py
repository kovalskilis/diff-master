import io
import re
from typing import List
from docx import Document
from sqlalchemy import func
from models.document import TaxUnit, TaxUnitType
import uuid


class DocumentParser:
    """
    FR-2: Parse documents into hierarchical tax_unit structure
    Парсит документ (DOCX или TXT) и создает иерархическую структуру
    """
    
    def extract_text_from_docx(self, content: bytes) -> str:
        """Extract plain text from DOCX file"""
        doc = Document(io.BytesIO(content))
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
        return '\n'.join(text)
    
    async def parse_document(
        self, 
        content: bytes, 
        source_type: str, 
        base_document_id: int,
        user_id: uuid.UUID
    ) -> List[TaxUnit]:
        """
        Parse document into hierarchical structure
        Пример структуры НК РФ:
        - Раздел I
          - Глава 1
            - Статья 1
              - Пункт 1
                - Подпункт а)
        """
        if source_type == "docx":
            text = self.extract_text_from_docx(content)
        else:
            text = content.decode('utf-8')
        
        tax_units = []
        lines = text.split('\n')
        
        # Stack to track current parent at each level
        parent_stack = [None]  # [section, chapter, article, clause]
        breadcrumbs_stack = []
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Detect structure based on patterns
            unit_type = None
            title = line
            parent = None
            
            # Раздел
            if re.match(r'^РАЗДЕЛ\s+[IVX]+', line, re.IGNORECASE):
                unit_type = TaxUnitType.section
                parent = None
                breadcrumbs_stack = [line]
                parent_stack = [None]
            
            # Глава
            elif re.match(r'^ГЛАВА\s+\d+', line, re.IGNORECASE):
                unit_type = TaxUnitType.chapter
                parent = tax_units[-1].id if tax_units and tax_units[-1].type == TaxUnitType.section else None
                if len(breadcrumbs_stack) > 0:
                    breadcrumbs_stack = breadcrumbs_stack[:1]
                breadcrumbs_stack.append(line)
            
            # Статья
            elif re.match(r'^Статья\s+\d+', line, re.IGNORECASE):
                unit_type = TaxUnitType.article
                # Find parent chapter
                for i in range(len(tax_units) - 1, -1, -1):
                    if tax_units[i].type == TaxUnitType.chapter:
                        parent = tax_units[i].id
                        break
                if len(breadcrumbs_stack) > 1:
                    breadcrumbs_stack = breadcrumbs_stack[:2]
                breadcrumbs_stack.append(line)
            
            # Пункт
            elif re.match(r'^\d+\.', line) or re.match(r'^\d+\)', line):
                unit_type = TaxUnitType.clause
                # Find parent article
                for i in range(len(tax_units) - 1, -1, -1):
                    if tax_units[i].type == TaxUnitType.article:
                        parent = tax_units[i].id
                        break
                if len(breadcrumbs_stack) > 2:
                    breadcrumbs_stack = breadcrumbs_stack[:3]
                breadcrumbs_stack.append(line[:50])  # First 50 chars
            
            # Подпункт
            elif re.match(r'^[а-я]\)', line, re.IGNORECASE):
                unit_type = TaxUnitType.sub_clause
                # Find parent clause
                for i in range(len(tax_units) - 1, -1, -1):
                    if tax_units[i].type == TaxUnitType.clause:
                        parent = tax_units[i].id
                        break
                if len(breadcrumbs_stack) > 3:
                    breadcrumbs_stack = breadcrumbs_stack[:4]
                breadcrumbs_stack.append(line[:50])
            
            # If we detected a structural element, create TaxUnit
            if unit_type:
                breadcrumbs_path = ' / '.join(breadcrumbs_stack)
                
                tax_unit = TaxUnit(
                    base_document_id=base_document_id,
                    type=unit_type,
                    parent_id=parent,
                    title=title,
                    breadcrumbs_path=breadcrumbs_path
                )
                
                # Note: We'll set fulltext_vector later with a trigger or manual update
                # For now, we can set it to None
                
                tax_units.append(tax_unit)
        
        # If no structure detected, create a single article
        if not tax_units:
            tax_unit = TaxUnit(
                base_document_id=base_document_id,
                type=TaxUnitType.article,
                parent_id=None,
                title="Весь документ",
                breadcrumbs_path="Весь документ"
            )
            tax_units.append(tax_unit)
        
        return tax_units

