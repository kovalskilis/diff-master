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
