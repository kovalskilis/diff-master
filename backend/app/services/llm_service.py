from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
import re
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

load_dotenv("/home/kit/Desktop/Lizon/diff-master/backend/.env")

# Import settings after loading env
from config import settings


class LLMService:
    """
    Service for LLM operations (OpenAI GPT / DeepSeek)
    Handles Phase 1 (extract edits) and Phase 2 (apply edits)
    """
    
    def __init__(self):
        # Use DeepSeek if API key is set, otherwise fall back to OpenAI
        if settings.DEEPSEEK_API_KEY:
            self.llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=0,
                openai_api_key=settings.DEEPSEEK_API_KEY,
                openai_api_base=settings.DEEPSEEK_BASE_URL,
                request_timeout=60,  # 60 second timeout
                max_retries=1  # Only 1 retry
            )
            print(f"[LLM] Initialized DeepSeek with model={settings.LLM_MODEL}")
        else:
            self.llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=0,
                openai_api_key=settings.OPENAI_API_KEY,
                request_timeout=60,  # 60 second timeout
                max_retries=1  # Only 1 retry
            )
            print(f"[LLM] Initialized OpenAI with model={settings.LLM_MODEL}")
    
    async def extract_edit_instructions(self, edits_text: str) -> List[Dict[str, Any]]:
        """
        FR-4 Phase 1: Extract edit instructions from text
        
        Input: Текст правок (например: "В пункте 7 статьи 6.1: а) слова 'рабочий день' дополнить...")
        Output: List of {
            "address": "статья 6.1, пункт 7",
            "instruction": "а) слова 'рабочий день' дополнить...",
            "full_text": "..."
        }
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты - эксперт по анализу правок в юридических документах (Налоговый Кодекс РФ).

Твоя задача: из текста правок извлечь структурированную информацию.

Для каждой правки извлеки:
1. "address" - адрес правки (например: "статья 6.1, пункт 7", "глава 2, статья 11")
2. "instruction" - текст инструкции правки (например: "а) слова 'рабочий день' дополнить словами '...'")
3. "full_text" - полный текст правки как есть

ВАЖНО:
- Адрес должен содержать статью/главу/пункт в том формате, как они упомянуты
- Если в одном месте несколько правок (а), б), в)), раздели их на отдельные записи
- Сохраняй оригинальный текст правок

Верни результат в формате JSON array:
[
  {{
    "address": "статья 6.1, пункт 7",
    "instruction": "а) слова 'рабочий день' дополнить словами 'календарный день'",
    "full_text": "В пункте 7 статьи 6.1: а) слова 'рабочий день' дополнить словами 'календарный день'"
  }},
  ...
]
"""),
            ("user", "{edits_text}")
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({"edits_text": edits_text})
        
        # Parse JSON from response
        try:
            content = response.content
            if not content:
                print("LLM returned empty response")
                return []
                
            # Extract JSON array from markdown code block if present
            if "```json" in content:
                content = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
                if content:
                    content = content.group(1)
            elif "```" in content:
                content = re.search(r'```\s*(\[.*?\])\s*```', content, re.DOTALL)
                if content:
                    content = content.group(1)
            
            if not content:
                print("No JSON content found in LLM response")
                return []
                
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response: {e}")
            print(f"Response: {response.content}")
            return []
        except Exception as e:
            print(f"Unexpected error parsing LLM response: {e}")
            return []
    
    async def apply_edit_instruction(
        self, 
        before_text: str, 
        instruction: str
    ) -> str:
        """
        FR-4 Phase 2: Apply edit instruction to text fragment
        
        Input:
        - before_text: Оригинальный текст статьи/пункта
        - instruction: Инструкция правки (например: "а) слова 'рабочий день' дополнить словами 'календарный день'")
        
        Output: Измененный текст (after_text)
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты - эксперт редактор юридических документов.

Твоя задача: применить правку к тексту согласно инструкции.

ВАЖНО:
- Применяй правку ТОЧНО как указано в инструкции
- Сохраняй форматирование и структуру текста
- Если инструкция говорит "слова ... заменить словами ...", найди эти слова и замени
- Если "дополнить словами", добавь слова в нужное место
- Если "исключить слова", удали их
- Если правку невозможно применить (текст не найден), верни исходный текст и укажи в начале: [ОШИБКА: текст не найден]

Верни ТОЛЬКО измененный текст, без комментариев."""),
            ("user", """Оригинальный текст:
{before_text}

Инструкция правки:
{instruction}

Примени правку и верни измененный текст:""")
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "before_text": before_text,
            "instruction": instruction
        })
        
        after_text = response.content.strip()
        return after_text
    
    async def match_address_to_breadcrumbs(
        self, 
        address: str, 
        available_breadcrumbs: List[str]
    ) -> Optional[str]:
        """
        Match extracted address to actual tax unit breadcrumbs
        Uses LLM for fuzzy matching
        
        Input:
        - address: "статья 6.1, пункт 7"
        - available_breadcrumbs: ["Раздел I / Глава 1 / Статья 6.1 / Пункт 7", ...]
        
        Output: Best matching breadcrumb or None
        """
        if not available_breadcrumbs:
            return None
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты помогаешь сопоставить адрес правки с полным путем в иерархии документа.

Дан адрес правки (например: "статья 6.1, пункт 7") и список доступных путей.

Найди наиболее подходящий путь из списка.

Верни только путь или "неизвестно" если не можешь найти подходящий."""),
            ("user", """Адрес правки: {address}

Доступные пути:
{available_breadcrumbs}

Найди наиболее подходящий путь:""")
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "address": address,
            "available_breadcrumbs": "\n".join(available_breadcrumbs)
        })
        
        result = response.content.strip()
        
        # Check if result matches any available breadcrumb
        for breadcrumb in available_breadcrumbs:
            if result.lower() in breadcrumb.lower() or breadcrumb.lower() in result.lower():
                return breadcrumb
        
        return None

    async def analyze_change_metadata(
        self,
        before_text: str,
        after_text: str,
        instruction: Optional[str] = None,
        article_number: Optional[str] = None
    ) -> dict:
        """
        Single LLM call to extract:
        - effective_date: DD.MM.YYYY or null
        - is_banking: boolean flag whether the change relates to the banking sector
        - confidence and short reason
        """
        # Build focused excerpts to reduce tokens
        def _changed_excerpts(src_before: str, src_after: str, context: int = 80, max_chars: int = 2000) -> tuple[str, str]:
            import difflib
            sm = difflib.SequenceMatcher(a=src_before or "", b=src_after or "")
            before_parts = []
            after_parts = []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                b_start = max(i1 - context, 0)
                b_end = min(i2 + context, len(src_before or ""))
                a_start = max(j1 - context, 0)
                a_end = min(j2 + context, len(src_after or ""))
                before_parts.append((src_before or "")[b_start:b_end])
                after_parts.append((src_after or "")[a_start:a_end])
                if sum(map(len, before_parts)) > max_chars or sum(map(len, after_parts)) > max_chars:
                    break
            return " … ".join(before_parts)[:max_chars], " … ".join(after_parts)[:max_chars]
        
        b_excerpt, a_excerpt = _changed_excerpts(before_text or "", after_text or "")
        text_for_llm = f"{instruction or ''}\n\nБЫЛО:\n{b_excerpt or (before_text or '')[:800]}\n\nСТАЛО:\n{a_excerpt or (after_text or '')[:800]}"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты аналитик изменений НК РФ.
Определи:
- дату вступления нормы в действие (формат ДД.ММ.ГГГГ), если упомянута;
- относится ли изменение к банковскому сегменту (банки, кредитные организации, банковские операции, надзор ЦБ РФ, банковские гарантии, вклады и т.п.).
Верни строго JSON:
{"effective_date": "ДД.ММ.ГГГГ" | null, "is_banking": true|false, "confidence": 0..1, "reason": "кратко"}"""),
            ("user", """{article_label}
{text}""")
        ])
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({
                "article_label": f"Статья {article_number}" if article_number else "",
                "text": text_for_llm[:6000]
            })
            raw = (response.content or "").strip()
            # Extract JSON if model wrapped it
            import re as _re
            parsed = raw
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            if m:
                parsed = m.group(0)
            data = json.loads(parsed)
            # Normalize fields
            eff = data.get("effective_date")
            if isinstance(eff, str):
                m2 = _re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', eff)
                data["effective_date"] = m2.group(1) if m2 else None
            else:
                data["effective_date"] = None if eff in (None, "", "нет", "none") else eff
            data["is_banking"] = bool(data.get("is_banking"))
            try:
                data["confidence"] = float(data.get("confidence", 0.0))
            except Exception:
                data["confidence"] = 0.0
            try:
                print(f"[ExportMeta] LLM_ANALYSIS: {data}")
            except Exception:
                pass
            return data
        except Exception as e:
            try:
                print(f"[ExportMeta] ERROR: {e}")
            except Exception:
                pass
            return {}

    def parse_edits_by_articles_sync(self, edits_content: str) -> Dict[str, str]:
        """
        Parse edits and group them by articles using LLM (synchronous version)
        """
        try:
            # Limit content size to prevent LLM timeout
            MAX_CONTENT_LENGTH = 16000  # characters (increased from 4000)
            if len(edits_content) > MAX_CONTENT_LENGTH:
                print(f"[LLM] Content too large ({len(edits_content)} chars), truncating to {MAX_CONTENT_LENGTH}")
                edits_content = edits_content[:MAX_CONTENT_LENGTH] + "\n\n[ТЕКСТ ОБРЕЗАН ДЛЯ ОБРАБОТКИ LLM]"
            
            print(f"[LLM] Processing content of {len(edits_content)} characters")
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Проанализируй текст правок и создай JSON с номерами статей как ключами. 
Для каждой статьи создай структурированное описание изменений в формате:

Статья X.X (Название статьи)
Пункт Y:
- Детальное описание изменения 1
- Детальное описание изменения 2

Пример:
{{
    "6.1": "Статья 6.1 (Порядок исчисления сроков)\\nПункт 7:\\n- Дополнить после слов \\"рабочий день\\" словами \\", за исключением срока уплаты налогов\\"\\n- Дополнить новым абзацем, устанавливающим, что если последний день срока уплаты налога выпадает на выходной/праздничный день, то днем окончания срока считается предшествующий рабочий день",
    "11": "Статья 11 (Институты, понятия и термины)\\nПункт 2:\\n- Изложить абзац 21 в новой редакции, уточняющей понятие \\"сезонное производство\\"\\n- Дополнить новым абзацем, определяющим понятие \\"Имущество\\" для целей НК РФ\\nПункт 5:\\n- Дополнить список организаций словами \\", государственную корпорацию \\"Агентство по страхованию вкладов\\"\\""
}}"""),
                ("user", "Проанализируй правки и структурируй по статьям:\n\n{content}")
            ])
            
            chain = prompt | self.llm
            
            # Use synchronous invoke instead of async
            try:
                print(f"[LLM] Sending synchronous request to LLM...")
                response = chain.invoke({"content": edits_content})
            except Exception as e:
                print(f"[LLM] Error during LLM request: {e}")
                return {}
            
            if not response or not response.content:
                print(f"[LLM] Empty response from LLM")
                return {}
            
            print(f"[LLM] Received response from LLM: {len(response.content)} characters")
            print(f"[LLM] Response preview: {response.content[:200]}...")
            
            # Parse JSON response
            try:
                response_text = response.content.strip()
                
                # Remove markdown code blocks if present
                if response_text.startswith("```json"):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.startswith("```"):
                    response_text = response_text[3:]   # Remove ```
                if response_text.endswith("```"):
                    response_text = response_text[:-3]  # Remove trailing ```
                
                response_text = response_text.strip()
                
                parsed_result = json.loads(response_text)
                print(f"[LLM] Successfully parsed {len(parsed_result)} article groups")
                return parsed_result
            except json.JSONDecodeError as e:
                print(f"[LLM] Failed to parse JSON response: {e}")
                print(f"[LLM] Raw response: {response.content}")
                print(f"[LLM] Processed response_text: {response_text}")
                return {}
                
        except Exception as e:
            print(f"[LLM] Error parsing edits by articles: {e}")
            return {}

    async def determine_target_article(
        self, 
        address: str, 
        available_articles: List[str]
    ) -> Optional[str]:
        """
        Determine which article the edit address targets
        
        Input:
        - address: "статья 6.1, пункт 7" or "в статье 11.3"
        - available_articles: ["1", "6.1", "11.3", "25"]
        
        Output: Article number (e.g., "6.1") or None
        """
        if not available_articles:
            return None
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты помогаешь определить, к какой статье относится правка.

Дан адрес правки (например: "статья 6.1, пункт 7") и список доступных статей.

Определи номер статьи из адреса и проверь, есть ли она в списке доступных.

Верни только номер статьи (например: "6.1") или "неизвестно" если не можешь определить."""),
            ("user", """Адрес правки: {address}

Доступные статьи: {available_articles}

Определи номер статьи:""")
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "address": address,
            "available_articles": ", ".join(available_articles)
        })
        
        result = response.content.strip()
        
        # Check if result is in available articles
        if result in available_articles:
            return result
        elif result.lower() in ["неизвестно", "unknown", "не знаю"]:
            return None
        else:
            # Try to extract article number from response
            import re
            match = re.search(r'(\d+(?:\.\d+)?)', result)
            if match and match.group(1) in available_articles:
                return match.group(1)
        
        return None

    async def summarize_edit(
        self,
        before_text: str,
        after_text: str,
        article_number: Optional[str] = None,
        instruction: Optional[str] = None
    ) -> str:
        """
        Create a very short Russian summary of what was changed.
        Returns 1-2 sentences suitable for the Excel 'КОММЕНТАРИИ' column.
        """
        # Truncate helper for safety
        def _truncate(text: str, limit: int) -> str:
            if not text:
                return ""
            if len(text) <= limit:
                return text
            return text[:limit] + " …"
        
        # Build focused excerpts around actual changes to avoid "без изменений"
        def _changed_excerpts(src_before: str, src_after: str, context: int = 80, max_chars: int = 1600) -> tuple[str, str, int]:
            import difflib
            if not src_before and not src_after:
                return "", "", 0
            sm = difflib.SequenceMatcher(a=src_before or "", b=src_after or "")
            opcodes = sm.get_opcodes()
            changed_blocks = [op for op in opcodes if op[0] != "equal"]
            
            if not changed_blocks:
                return "", "", 0
            
            before_parts = []
            after_parts = []
            consumed_before = 0
            consumed_after = 0
            
            for tag, i1, i2, j1, j2 in changed_blocks:
                # Add local context around the change
                b_start = max(i1 - context, 0)
                b_end = min(i2 + context, len(src_before or ""))
                a_start = max(j1 - context, 0)
                a_end = min(j2 + context, len(src_after or ""))
                
                before_piece = (src_before or "")[b_start:b_end]
                after_piece = (src_after or "")[a_start:a_end]
                
                before_parts.append(before_piece)
                after_parts.append(after_piece)
                
                consumed_before += len(before_piece)
                consumed_after += len(after_piece)
                
                # Stop once we hit limits
                if consumed_before >= max_chars or consumed_after >= max_chars:
                    break
            
            before_excerpt = " … ".join(before_parts)[:max_chars]
            after_excerpt = " … ".join(after_parts)[:max_chars]
            return before_excerpt, after_excerpt, len(changed_blocks)
        
        # Prefer focused excerpts of actual changes; fall back to head truncation
        before_excerpt, after_excerpt, blocks = _changed_excerpts(before_text or "", after_text or "")
        if blocks == 0:
            before_short = _truncate(before_text or "", 2000)
            after_short = _truncate(after_text or "", 2000)
        else:
            before_short = _truncate(before_excerpt, 1800)
            after_short = _truncate(after_excerpt, 1800)
        
        # Compute simple diff statistics for guardrails and logging
        def _diff_stats(a: str, b: str) -> dict:
            import difflib
            sm = difflib.SequenceMatcher(a=a or "", b=b or "")
            stats = {"added": 0, "deleted": 0, "replaced": 0, "equal": 0}
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "insert":
                    stats["added"] += j2 - j1
                elif tag == "delete":
                    stats["deleted"] += i2 - i1
                elif tag == "replace":
                    stats["replaced"] += max(i2 - i1, j2 - j1)
                elif tag == "equal":
                    stats["equal"] += max(i2 - i1, j2 - j1)
            stats["changed_blocks"] = sum(1 for t in sm.get_opcodes() if t[0] != "equal")
            return stats
        
        stats = _diff_stats(before_text or "", after_text or "")
        
        instruction_short = _truncate(instruction or "", 800)
        article_label = f"Статья {article_number}" if article_number else "Статья"
        
        # Debug log for diagnostics
        try:
            print(
                f"[ExportSummary] {article_label}: before_len={len(before_text or '')}, after_len={len(after_text or '')}, "
                f"changed_blocks={blocks}, instr_len={len(instruction or '')}"
            )
            print(f"[ExportSummary] BEFORE_EXCERPT: {before_short[:400]!r}")
            print(f"[ExportSummary] AFTER_EXCERPT: {after_short[:400]!r}")
            if instruction_short:
                print(f"[ExportSummary] INSTRUCTION: {instruction_short[:300]!r}")
        except Exception:
            pass
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты выступаешь как юрист‑редактор. 
Сформулируй краткий комментарий (1–2 коротких предложения) о сути внесённой правки.
Говори по‑делу, без Markdown и без списков. Не используй вводные фразы вроде "Внесена правка".
Если дана инструкция, учитывай её, но не цитируй дословно.
Язык ответа — русский."""),
            ("user", """Контекст: {article_label}

Инструкция (если есть):
{instruction}

Было:
{before}

Стало:
{after}

Дай короткий комментарий (1–2 предложения):""")
        ])
        
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({
                "article_label": article_label,
                "instruction": instruction_short or "—",
                "before": before_short,
                "after": after_short
            })
            summary = (response.content or "").strip()
            # Ensure the comment is compact
            if len(summary) > 400:
                summary = summary[:400].rstrip() + " …"
            # Safety: strip accidental code fences or formatting
            summary = summary.replace("```", "").strip()
            try:
                print(f"[ExportSummary] LLM_SUMMARY: {summary!r}")
                print(f"[ExportSummary] DIFF_STATS: {stats}")
            except Exception:
                pass
            
            # Guardrail: if LLM утверждает, что изменений нет, а diff их показывает — переписываем комментарий
            lower = summary.lower()
            if stats.get("changed_blocks", 0) > 0 and (
                "без измен" in lower or "no change" in lower or "нет измен" in lower
            ):
                # Сформируем детерминированный краткий комментарий по статистике отличий
                added = stats.get("added", 0)
                deleted = stats.get("deleted", 0)
                replaced = stats.get("replaced", 0)
                key_after = after_short.splitlines()
                key_snippet = ""
                for line in key_after:
                    if len(line.strip()) > 0:
                        key_snippet = line.strip()
                        break
                rule_based = f"{article_label}: изменения обнаружены — добавлено {added} симв., удалено {deleted}, изменено {replaced}. Пример: {key_snippet[:160]}".strip()
                try:
                    print(f"[ExportSummary] OVERRIDDEN_SUMMARY: {rule_based!r}")
                except Exception:
                    pass
                return rule_based
            return summary or "Краткое описание изменения недоступно"
        except Exception as e:
            # Fall back to a minimal heuristic if LLM fails
            # Use deterministic diff-based fallback first
            if stats.get("changed_blocks", 0) > 0:
                added = stats.get("added", 0)
                deleted = stats.get("deleted", 0)
                replaced = stats.get("replaced", 0)
                return f"{article_label}: изменения — добавлено {added} симв., удалено {deleted}, изменено {replaced}."
            if instruction_short:
                return f"Кратко: {instruction_short[:200]}".strip()
            return "Изменение статьи; подробности см. в колонках 'Было' и 'Стало'."

    async def extract_effective_date(self, text: str) -> Optional[str]:
        """
        Try to extract a single effective date from Russian legal text.
        Returns date as DD.MM.YYYY or None if not found.
        """
        if not text:
            return None
        
        # Fast path: regex dd.mm.yyyy near 'вступ'
        import re
        candidates = []
        for m in re.finditer(r'вступ\w{0,10}[^\.]{0,120}?(\d{1,2}\.\d{1,2}\.\d{4})', text, flags=re.IGNORECASE | re.DOTALL):
            try:
                candidates.append(m.group(1))
            except Exception:
                pass
        if candidates:
            # Prefer the first occurrence
            return candidates[0]
        
        # Use LLM as fallback
        try:
            snippet = text
            if len(snippet) > 3000:
                snippet = snippet[:3000]
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Ты извлекаешь дату вступления нормы в силу.
Верни ТОЛЬКО дату формата ДД.ММ.ГГГГ. Если даты нет — верни слово 'нет'."""),
                ("user", "{text}")
            ])
            chain = prompt | self.llm
            response = await chain.ainvoke({"text": snippet})
            content = (response.content or "").strip()
            # Extract strict dd.mm.yyyy
            m = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', content)
            if m:
                return m.group(1)
        except Exception:
            pass
        
        return None
