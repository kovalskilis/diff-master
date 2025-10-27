from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import uuid
import asyncio
import os
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from .celery_app import celery_app
from config import settings
from models.document import (
    WorkspaceFile, EditTarget, EditJobStatus, TaxUnit, 
    PatchedFragment, ChangeType, BaseDocument
)
from services.llm_service import LLMService


# Create sync engine for Celery tasks
sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))


class DatabaseTask(Task):
    """Base task with database session"""
    _session = None
    
    @property
    def session(self):
        if self._session is None:
            self._session = Session(sync_engine)
        return self._session
    
    def after_return(self, *args, **kwargs):
        if self._session is not None:
            self._session.close()
            self._session = None
    
    def _fuzzy_match_address(self, address: str, tax_units):
        """Simple fuzzy matching for addresses"""
        address_lower = address.lower()
        
        # Try to extract numbers from address
        import re
        numbers = re.findall(r'\d+', address)
        
        for unit in tax_units:
            if not unit.breadcrumbs_path:
                continue
            
            path_lower = unit.breadcrumbs_path.lower()
            
            # Check if address keywords are in breadcrumbs
            if "статья" in address_lower and "статья" in path_lower:
                # Try to match article number
                for num in numbers:
                    if f"статья {num}" in path_lower or f"статья {num}." in path_lower:
                        return unit.id
            
            # Similar checks for other levels...
        
        return None
    
    def _determine_target_article(self, address: str, document_structure: dict, llm_service, loop):
        """Determine which article the edit targets using simple regex matching"""
        if not document_structure:
            return None
            
        # Extract article numbers from available structure
        available_articles = list(document_structure.keys())
        
        if not available_articles:
            return None
        
        # Use simple regex matching instead of LLM to avoid API issues
        import re
        
        # Extract article number from address using regex
        # Patterns: "статья 6.1", "в статье 11.3", "статья 25"
        patterns = [
            r'статья\s+(\d+(?:\.\d+)?)',
            r'в\s+статье\s+(\d+(?:\.\d+)?)',
            r'ст\.\s*(\d+(?:\.\d+)?)',
            r'статьи\s+(\d+(?:\.\d+)?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, address.lower())
            if match:
                article_num = match.group(1)
                if article_num in available_articles:
                    print(f"[Phase1] Found article {article_num} in address: {address}")
                    return article_num
        
        print(f"[Phase1] Could not determine article from address: {address}")
        return None


def _group_edits_by_article(self, edit_instructions: list, document_structure: dict) -> tuple:
    """Group edit instructions by target article"""
    article_groups = {}
    ungrouped_edits = []
    
    for instruction_data in edit_instructions:
        address = instruction_data.get("address", "")
        target_article = self._determine_target_article(address, document_structure, None, None)
        
        if target_article:
            if target_article not in article_groups:
                article_groups[target_article] = []
            article_groups[target_article].append(instruction_data)
        else:
            ungrouped_edits.append(instruction_data)
    
    return article_groups, ungrouped_edits

def _extract_instructions_regex(self, text: str) -> list:
    """Extract edit instructions using regex patterns"""
    import re
    
    instructions = []
    
    # Look for article patterns
    article_patterns = [
        r'Статья\s+(\d+(?:\.\d+)?)\s*[:\-]?\s*(.*?)(?=Статья\s+\d+|$)',
        r'статья\s+(\d+(?:\.\d+)?)\s*[:\-]?\s*(.*?)(?=статья\s+\d+|$)',
        r'В\s+статье\s+(\d+(?:\.\d+)?)\s*[:\-]?\s*(.*?)(?=В\s+статье\s+\d+|$)',
    ]
    
    for pattern in article_patterns:
        matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            article_num = match.group(1)
            content = match.group(2).strip()
            
            if content and len(content) > 10:  # Only meaningful content
                instructions.append({
                    "address": f"статья {article_num}",
                    "instruction": content[:1000],  # Limit length
                    "full_text": content
                })
    
    # If no articles found, create a general instruction
    if not instructions:
        # Look for any meaningful text patterns
        if "изменени" in text.lower() or "дополнить" in text.lower() or "исключить" in text.lower():
            instructions.append({
                "address": "общие изменения",
                "instruction": text[:1000],
                "full_text": text
            })
        else:
            # Fallback - use the whole text
            instructions.append({
                "address": "неизвестно",
                "instruction": text[:1000],
                "full_text": text
            })
    
    print(f"[Phase1] Regex extracted {len(instructions)} instructions")
    return instructions

def _process_article_edits(self, article_num: str, edits: list, document_structure: dict, 
                          tax_units: list, llm_service, loop) -> list:
    """Process edits for a specific article"""
    print(f"[Phase1] Processing {len(edits)} edits for article {article_num}")
    
    article_content = document_structure.get(article_num, {}).get('content', '')
    article_tax_units = [unit for unit in tax_units if article_num in (unit.breadcrumbs_path or '')]
    
    print(f"[Phase1] Article {article_num}: {len(article_tax_units)} tax units, {len(article_content)} chars content")
    
    targets = []
    
    # If we have article content, use it for more precise matching
    if article_content and llm_service and loop:
        print(f"[Phase1] Using article-specific content for LLM processing")
        try:
            # Process all edits for this article together with the article content
            article_edits_text = '\n\n'.join(edits)
            
            # Use LLM to find targets within the specific article
            matched_targets = loop.run_until_complete(
                asyncio.wait_for(
                    self._find_targets_in_article(
                        article_content, 
                        article_edits_text, 
                        article_tax_units,
                        llm_service
                    ),
                    timeout=15.0
                )
            )
            
            for target in matched_targets:
                targets.append({
                    "instruction": target.get("instruction", ""),
                    "tax_unit_id": target.get("tax_unit_id"),
                    "conflicts": target.get("conflicts", {})
                })
                
        except Exception as e:
            print(f"[Phase1] Error in article-specific processing: {e}")
            # Fallback to individual processing
            targets = self._process_edits_individually(edits, article_tax_units, llm_service, loop)
    else:
        # Fallback to individual processing
        targets = self._process_edits_individually(edits, article_tax_units, llm_service, loop)
    
    return targets

def _process_unknown_edits(self, edits: list, tax_units: list, llm_service, loop) -> list:
    """Process edits where article number could not be determined"""
    print(f"[Phase1] Processing {len(edits)} unknown edits")
    
    targets = []
    
    # For unknown edits, try to match against all tax units
    for edit in edits:
        print(f"[Phase1] Processing unknown edit: {edit[:100]}...")
        
        matched_tax_unit = None
        if llm_service and loop and tax_units:
            try:
                matched_tax_unit = loop.run_until_complete(
                    asyncio.wait_for(
                        self._match_address_to_breadcrumbs(
                            edit, 
                            tax_units, 
                            llm_service
                        ),
                        timeout=10.0
                    )
                )
            except Exception as e:
                print(f"[Phase1] Error matching unknown edit: {e}")
        
        targets.append({
            "instruction": edit,
            "tax_unit_id": matched_tax_unit.id if matched_tax_unit else None,
            "conflicts": {
                "error": "Could not match address to tax unit" if not matched_tax_unit else None,
                "address": "неизвестно"
            }
        })
    
    return targets

def _process_edits_individually(self, edits: list, tax_units: list, llm_service, loop) -> list:
    """Process edits individually when article-specific processing fails"""
    targets = []
    
    for edit in edits:
        matched_tax_unit = None
        if llm_service and loop and tax_units:
            try:
                matched_tax_unit = loop.run_until_complete(
                    asyncio.wait_for(
                        self._match_address_to_breadcrumbs(
                            edit, 
                            tax_units, 
                            llm_service
                        ),
                        timeout=10.0
                    )
                )
            except Exception as e:
                print(f"[Phase1] Error matching edit: {e}")
        
        targets.append({
            "instruction": edit,
            "tax_unit_id": matched_tax_unit.id if matched_tax_unit else None,
            "conflicts": {
                "error": "Could not match address to tax unit" if not matched_tax_unit else None,
                "address": "неизвестно"
            }
        })
    
    return targets

async def _find_targets_in_article(self, article_content: str, edits_text: str, 
                                  tax_units: list, llm_service) -> list:
    """
    Find edit targets within a specific article using LLM
    """
    try:
        # Create a focused prompt for this specific article
        prompt = f"""
        Найди точные места в тексте статьи, к которым относятся правки.

        ТЕКСТ СТАТЬИ:
        {article_content[:8000]}  # Limit content to avoid token limits

        ПРАВКИ ДЛЯ ЭТОЙ СТАТЬИ:
        {edits_text[:2000]}  # Limit edits text

        Верни JSON массив с найденными целями:
        [
            {{
                "instruction": "текст правки",
                "target_text": "найденный фрагмент в статье",
                "position": "примерное место в статье",
                "confidence": 0.8
            }}
        ]
        """
        
        response = await llm_service.llm.ainvoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        import json
        try:
            if "```json" in content:
                content = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
                if content:
                    content = content.group(1)
            
            targets = json.loads(content)
            
            # Match targets to tax units
            matched_targets = []
            for target in targets:
                instruction = target.get("instruction", "")
                target_text = target.get("target_text", "")
                
                # Find best matching tax unit
                best_match = None
                best_score = 0
                
                for tax_unit in tax_units:
                    if target_text.lower() in tax_unit.current_version.text_content.lower():
                        score = len(target_text) / len(tax_unit.current_version.text_content)
                        if score > best_score:
                            best_score = score
                            best_match = tax_unit
                
                matched_targets.append({
                    "instruction": instruction,
                    "tax_unit_id": best_match.id if best_match else None,
                    "conflicts": {
                        "error": "Could not match to tax unit" if not best_match else None,
                        "target_text": target_text,
                        "confidence": target.get("confidence", 0)
                    }
                })
            
            return matched_targets
            
        except json.JSONDecodeError as e:
            print(f"[Phase1] Error parsing LLM response: {e}")
            return []
            
    except Exception as e:
        print(f"[Phase1] Error in _find_targets_in_article: {e}")
        return []

@celery_app.task(base=DatabaseTask, bind=True)
def phase1_find_targets_approved(self, user_id: str, document_id: int, approved_articles: dict):
    """
    Process pre-approved edits by articles
    """
    print(f"[Phase1-Approved] Starting for document_id={document_id}, user_id={user_id}")
    
    try:
        # Get document
        from models.document import BaseDocument, TaxUnit, EditTarget, EditJobStatus
        result = self.session.execute(
            select(BaseDocument).where(
                BaseDocument.id == document_id,
                BaseDocument.user_id == user_id
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            return {"error": "Document not found"}
        
        # Get document structure
        document_structure = document.structure or {}
        print(f"[Phase1-Approved] Document structure: {len(document_structure)} articles")
        
        # Get tax units
        tax_units = self.session.execute(
            select(TaxUnit).where(TaxUnit.base_document_id == document_id)
        )
        tax_units = tax_units.scalars().all()
        print(f"[Phase1-Approved] Found {len(tax_units)} tax units")
        
        # Process each approved article
        all_created_targets = []
        
        for article_num, article_content in approved_articles.items():
            if article_num == "unknown":
                continue
                
            print(f"[Phase1-Approved] Processing article {article_num}")
            
            # Find tax units for this article
            article_tax_units = [
                unit for unit in tax_units 
                if article_num in (unit.breadcrumbs_path or '')
            ]
            
            # Create edit targets for this article
            edit_target = EditTarget(
                user_id=user_id,
                workspace_file_id=None,  # No workspace file for approved edits
                status=EditJobStatus.review,
                instruction_text=article_content,
                initial_tax_unit_id=None,
                confirmed_tax_unit_id=None,
                conflicts_json={
                    "article": article_num,
                    "source": "approved_edits",
                    "content_length": len(article_content)
                }
            )
            self.session.add(edit_target)
            all_created_targets.append({
                "instruction": article_content,
                "article": article_num,
                "tax_unit_id": None
            })
        
        self.session.commit()
        
        print(f"[Phase1-Approved] SUCCESS: Created {len(all_created_targets)} targets")
        return {
            "status": "success",
            "targets_created": len(all_created_targets),
            "articles_processed": len([k for k in approved_articles.keys() if k != "unknown"]),
            "targets": all_created_targets
        }
        
    except Exception as e:
        self.session.rollback()
        print(f"[Phase1-Approved] ERROR: {e}")
        return {"error": str(e)}


@celery_app.task(base=DatabaseTask, bind=True)
def phase1_find_targets(self, workspace_file_id: int, user_id: str):
    """
    FR-4 Phase 1: Find edit targets (LLM VERSION)
    
    Uses LLM parsing for intelligent grouping of edits by articles
    """
    session = self.session
    user_uuid = uuid.UUID(user_id)
    
    try:
        print(f"[Phase1] Starting LLM-PARSING for workspace_file_id={workspace_file_id}, user_id={user_id}")
        
        # Get workspace file
        workspace_file = session.query(WorkspaceFile).filter(
            WorkspaceFile.id == workspace_file_id,
            WorkspaceFile.user_id == user_uuid
        ).first()
        
        if not workspace_file:
            print(f"[Phase1] ERROR: Workspace file {workspace_file_id} not found")
            return {"error": "Workspace file not found"}
        
        if not workspace_file.raw_payload_text:
            print(f"[Phase1] ERROR: Workspace file {workspace_file_id} has no text content")
            return {"error": "Workspace file has no text content"}
        
        print(f"[Phase1] Found workspace file with {len(workspace_file.raw_payload_text)} chars of text")
        
        # Check if content is too large for LLM
        if len(workspace_file.raw_payload_text) > 10000:
            print(f"[Phase1] WARNING: Content is very large ({len(workspace_file.raw_payload_text)} chars), LLM may timeout")
        
        # Get base document and its structure
        base_document = session.query(BaseDocument).filter(
            BaseDocument.id == workspace_file.base_document_id
        ).first()
        
        if not base_document:
            print(f"[Phase1] ERROR: Base document not found")
            return {"error": "Base document not found"}
        
        # Get document structure for article targeting
        document_structure = base_document.structure or {}
        print(f"[Phase1] Document has {len(document_structure)} articles")
        
        # Parse edits using LLM
        print(f"[Phase1] Parsing edits using LLM...")
        
        # Use LLM to parse edits by articles
        llm_service = LLMService()
        
        # Use synchronous LLM parsing
        try:
            parsed_edits = llm_service.parse_edits_by_articles_sync(workspace_file.raw_payload_text)
        except Exception as e:
            print(f"[Phase1] Error during LLM operation: {e}")
            parsed_edits = {}
        
        print(f"[Phase1] LLM parsing completed, result: {len(parsed_edits) if parsed_edits else 0} articles")
        
        if not parsed_edits:
            print(f"[Phase1] ERROR: LLM failed to parse edits")
            return {"error": "LLM failed to parse edits from file"}
        
        print(f"[Phase1] Parsed {len(parsed_edits)} articles: {list(parsed_edits.keys())}")
        
        # Get tax units for matching
        tax_units = session.query(TaxUnit).filter(
            TaxUnit.base_document_id == workspace_file.base_document_id
        ).all()
        print(f"[Phase1] Found {len(tax_units)} tax units")
        
        # Check if we have any articles to process
        if not parsed_edits:
            print(f"[Phase1] WARNING: No articles found in file")
            return {"error": "No articles found in file"}
        
        # Process each article
        all_created_targets = []
        
        for article_num, article_content in parsed_edits.items():
            if article_num == "unknown":
                continue
                
            print(f"[Phase1] Processing article {article_num}")
            
            # Проверить, не создана ли уже задача для этой статьи
            # Более безопасная проверка через to_tsquery для JSONB
            import json
            article_filter = json.dumps({"article": article_num})
            
            existing_target = session.query(EditTarget).filter(
                EditTarget.workspace_file_id == workspace_file_id,
                EditTarget.user_id == user_uuid
            ).filter(
                EditTarget.conflicts_json['article'].astext == article_num
            ).first()
            
            if existing_target:
                print(f"[Phase1] Target for article {article_num} already exists, skipping")
                continue
            
            # Find tax units for this article
            article_tax_units = [
                unit for unit in tax_units 
                if article_num in (unit.breadcrumbs_path or '')
            ]
            
            print(f"[Phase1] Article {article_num}: {len(article_tax_units)} tax units found")
            
            # Create edit target for this article
            edit_target = EditTarget(
                user_id=user_uuid,
                workspace_file_id=workspace_file_id,
                status=EditJobStatus.review,
                instruction_text=article_content,
                initial_tax_unit_id=None,
                confirmed_tax_unit_id=None,
                conflicts_json={
                    "article": article_num,
                    "source": "llm_structured_parsing",
                    "content_length": len(article_content),
                    "tax_units_found": len(article_tax_units),
                    "structured_format": True
                }
            )
            session.add(edit_target)
            all_created_targets.append({
                "instruction": article_content,
                "article": article_num,
                "tax_unit_id": None
            })
        
        session.commit()
        
        print(f"[Phase1] SUCCESS: Created {len(all_created_targets)} targets")
        return {
            "status": "success",
            "targets_created": len(all_created_targets),
            "articles_processed": len([k for k in parsed_edits.keys() if k != "unknown"]),
            "unknown_edits": 1 if "unknown" in parsed_edits else 0,
            "targets": all_created_targets
        }
    
    except Exception as e:
        session.rollback()
        print(f"[Phase1] EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    
    finally:
        session.close()


@celery_app.task(base=DatabaseTask, bind=True)
def phase2_apply_edits(self, workspace_file_id: int, user_id: str):
    """
    FR-4 Phase 2: Apply edits to confirmed targets
    
    1. Get all EditTargets with confirmed_tax_unit_id
    2. For each target:
       - Get before_text from tax_unit's current version
       - Use LLM to apply instruction
       - Create PatchedFragment with before/after
    """
    session = self.session
    user_uuid = uuid.UUID(user_id)
    
    try:
        # Get all edit targets for this workspace file
        edit_targets = session.query(EditTarget).filter(
            EditTarget.workspace_file_id == workspace_file_id,
            EditTarget.user_id == user_uuid,
            EditTarget.confirmed_tax_unit_id.isnot(None)
        ).all()
        
        if not edit_targets:
            return {"error": "No confirmed edit targets found"}
        
        # Get workspace file
        workspace_file = session.query(WorkspaceFile).filter(
            WorkspaceFile.id == workspace_file_id
        ).first()
        
        if not workspace_file:
            return {"error": "Workspace file not found"}
        
        # Initialize LLM service
        llm_service = LLMService()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        applied_count = 0
        
        # Get base document and its structure for article-specific editing
        base_document = session.query(BaseDocument).filter(
            BaseDocument.id == workspace_file.base_document_id
        ).first()
        
        document_structure = base_document.structure if base_document else {}
        
        for target in edit_targets:
            # Get tax_unit and its current version
            tax_unit = session.query(TaxUnit).filter(
                TaxUnit.id == target.confirmed_tax_unit_id
            ).first()
            
            if not tax_unit:
                continue
            
            # Try to get article-specific content for more precise editing
            before_text = ""
            target_article = None
            
            # Extract article number from breadcrumbs if possible
            if tax_unit.breadcrumbs_path:
                import re
                article_match = re.search(r'Статья\s+(\d+(?:\.\d+)?)', tax_unit.breadcrumbs_path)
                if article_match:
                    target_article = article_match.group(1)
            
            # Use article content if available, otherwise fall back to tax unit content
            if target_article and target_article in document_structure:
                before_text = document_structure[target_article]['content']
                print(f"[Phase2] Using article {target_article} content ({len(before_text)} chars)")
            else:
                # Fallback to tax unit content
                from models.document import TaxUnitVersion
                current_version = None
                if tax_unit.current_version_id:
                    current_version = session.query(TaxUnitVersion).filter(
                        TaxUnitVersion.id == tax_unit.current_version_id
                    ).first()
                
                before_text = current_version.text_content if current_version else (tax_unit.title or "")
                print(f"[Phase2] Using tax unit content ({len(before_text)} chars)")
            
            # Apply edit using LLM with article-specific content
            after_text = loop.run_until_complete(
                llm_service.apply_edit_instruction(
                    before_text=before_text,
                    instruction=target.instruction_text
                )
            )
            
            # Check if LLM returned error
            change_type = ChangeType.modified
            if "[ОШИБКА:" in after_text:
                change_type = ChangeType.modified  # Still mark as modified but with error
            
            # Create PatchedFragment
            patched_fragment = PatchedFragment(
                user_id=user_uuid,
                edit_target_id=target.id,
                tax_unit_id=tax_unit.id,
                before_text=before_text,
                after_text=after_text,
                change_type=change_type,
                metadata_json={
                    "instruction": target.instruction_text,
                    "has_error": "[ОШИБКА:" in after_text
                }
            )
            session.add(patched_fragment)
            
            # Update target status
            target.status = EditJobStatus.completed
            
            applied_count += 1
        
        session.commit()
        loop.close()
        
        return {
            "status": "success",
            "edits_applied": applied_count
        }
    
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    
    finally:
        session.close()

