from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
import re
import os
from pathlib import Path

# Load environment variables
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Only load .env file if NOT running inside Docker
if os.getenv("DISABLE_DOTENV") != "1":
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[LLM] Loaded .env from: {env_path}")
    else:
        print(f"[LLM] .env not found at {env_path}, using OS environment")
else:
    print("[LLM] DISABLE_DOTENV=1, using Docker environment variables")

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
                request_timeout=300,  # increased timeout to handle long edits
                max_retries=2,
                max_tokens=16000  # Allow long responses for large articles
            )
            print(f"[LLM] Initialized DeepSeek with model={settings.LLM_MODEL}, max_tokens=16000")
        else:
            self.llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=0,
                openai_api_key=settings.OPENAI_API_KEY,
                request_timeout=300,  # increased timeout to handle long edits
                max_retries=2,
                max_tokens=16000  # Allow long responses for large articles
            )
            print(f"[LLM] Initialized OpenAI with model={settings.LLM_MODEL}, max_tokens=16000")
    
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
        
        Uses a diff-based approach: LLM returns only find/replace pairs,
        then changes are applied programmatically to preserve full text.
        This avoids output token limits for large articles.
        
        Input:
        - before_text: Оригинальный текст статьи/пункта
        - instruction: Инструкция правки
        
        Output: Измененный текст (after_text)
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Ты - эксперт редактор юридических документов.

Твоя задача: определить КОНКРЕТНЫЕ замены в тексте согласно инструкции.

КРИТИЧЕСКИ ВАЖНО:
- Если инструкция упоминает конкретный пункт (например, "в пункте 17.2", "пункт 17.2-1"), 
  ты ДОЛЖЕН найти этот пункт в оригинальном тексте и применять правки ТОЛЬКО к нему
- Пункты в тексте могут быть обозначены как "17.2.", "17.2)", "п. 17.2", "пункт 17.2" и т.д.
- Ищи пункт по его номеру (17.2, 17.2-1 и т.д.) в тексте статьи
- НЕ применяй правки к другим пунктам или ко всей статье
- НЕ дублируй текст из других пунктов

КРИТИЧЕСКИ ВАЖНО ДЛЯ МНОЖЕСТВЕННЫХ ЗАМЕН:
- Если инструкция содержит несколько правок (например, замена слова И добавление абзаца),
  ВСЕ замены должны быть применимы к ИСХОДНОМУ тексту, который ты видишь в "Оригинальный текст"
- НЕ используй в "find" текст, который будет изменен предыдущей заменой
- Если нужно заменить "агента;" на "агента." И добавить абзац после этого:
  * Первая замена: find = "агента;", replace = "агента."
  * Вторая замена (добавление абзаца): find = "агента;" (ИСХОДНЫЙ текст, не "агента."!), 
    replace = "агента;" + перенос строки + новый абзац
  * Или лучше: find = конец абзаца с "агента;" (из исходного текста), 
    replace = тот же конец + перенос строки + новый абзац

- Если инструкция говорит "дополнить абзацем десятым пункта 17.2" или "дополнить абзацем [номер]":
  1) Найди в ИСХОДНОМ тексте пункт 17.2 (ищи по номеру "17.2" в начале строки или после слова "пункт")
  2) Найди в этом пункте последний абзац в ИСХОДНОМ тексте (обычно это абзац, который заканчивается точкой с запятой ";" или точкой ".")
  3) В "find" включи КОНЕЦ последнего абзаца пункта 17.2 из ИСХОДНОГО текста (последние 30-50 символов, включая точку с запятой или точку)
  4) В "replace" включи тот же текст из "find" + символ переноса строки (\n) + новый абзац целиком (как указано в инструкции в кавычках)
  5) НЕ добавляй абзац в другие пункты (17.2-1, 17.1 и т.д.)
  6) ОБЯЗАТЕЛЬНО добавь новый абзац - это критически важно!
  7) Если перед добавлением абзаца нужно заменить слово, используй ИСХОДНЫЙ текст в "find" для добавления абзаца
- Если нужно заменить текст в пункте, найди точный фрагмент внутри этого пункта и замени его

Верни результат СТРОГО в формате JSON-массива замен:
```json
[
  {{"find": "точная строка из оригинала которую нужно заменить", "replace": "новая строка на замену"}},
  {{"find": "другая строка для замены", "replace": "её замена"}}
]
```

ПРАВИЛА ПОИСКА ПУНКТОВ:
- Пункты в тексте могут начинаться с: "17.2.", "17.2)", "п. 17.2", "пункт 17.2", "17.2 " и т.д.
- Ищи пункт по его номеру (например, "17.2") в тексте - он может быть в начале строки или после слова "пункт"
- Если инструкция говорит "дополнить абзацем десятым пункта 17.2" или содержит "дополнить абзацем":
  * Найди в тексте пункт 17.2 (ищи строку, содержащую "17.2" в начале или после "пункт")
  * Найди последний абзац этого пункта (обычно это абзац, который заканчивается точкой с запятой ";" или точкой ".")
  * В "find" включи КОНЕЦ последнего абзаца пункта 17.2 (последние 30-50 символов, включая знак препинания в конце)
  * В "replace" включи тот же текст из "find" + символ переноса строки (\n) + новый абзац целиком (как указано в инструкции)
  * Новый абзац должен быть добавлен С ОБЯЗАТЕЛЬНО - это критически важно для выполнения инструкции!

ПРАВИЛА ФОРМАТИРОВАНИЯ:
- "find" должен содержать ТОЧНУЮ подстроку из оригинального текста (включая пробелы и переносы)
- "find" должен включать контекст, который однозначно идентифицирует нужный пункт (например, начало пункта 17.2 или его последний абзац)
- "replace" — то, на что нужно заменить
- Для ДОБАВЛЕНИЯ текста (особенно "дополнить абзацем"):
  * find = КОНЕЦ последнего абзаца пункта (последние 30-50 символов с знаками препинания)
  * replace = тот же текст из find + символ переноса строки (\n) + новый абзац целиком
  * ОБЯЗАТЕЛЬНО добавь новый абзац - не пропускай эту операцию!
- Для УДАЛЕНИЯ текста: find = удаляемый фрагмент, replace = ""
- Для ЗАМЕНЫ: find = старый текст, replace = новый текст
- Делай find достаточно длинным (20-60 символов) чтобы однозначно идентифицировать место
- НИКОГДА не используй многоточие "..." или "…" для сокращения текста в find или replace
- В "replace" указывай ПОЛНЫЙ текст замены, включая все ссылки на законы, номера, даты — ничего не пропускай и не сокращай
- Если в инструкции указано дополнить текст, в "replace" включи ВЕСЬ оригинальный фрагмент из "find" + добавленный текст целиком
- Если правку невозможно применить, верни: [{{"find": "", "replace": "", "error": "описание ошибки"}}]

ПРИМЕР для множественных замен (замена слова + добавление абзаца):
Инструкция: "в абзаце девятом слово 'агента;' заменить словом 'агента.'; дополнить абзацем десятым..."

Исходный текст содержит абзац, заканчивающийся: "...агента;"

ПРАВИЛЬНО (одна замена, которая делает и замену, и добавление):
[
  {{"find": "...агента;", "replace": "...агента.\nВ непрерывный срок нахождения в собственности налогоплательщика ценных бумаг, указанных в абзаце первом настоящего пункта, включается срок, в течение которого такие ценные бумаги выбыли из собственности налогоплательщика по договору займа ценными бумагами с брокером и (или) по договору репо;"}}
]

Где "..." - это конец абзаца (последние 30-50 символов), включая "агента;"
В replace: тот же конец, но "агента." вместо "агента;" + перенос строки + новый абзац

ВАЖНО: Если есть замена слова И добавление абзаца, объедини их в ОДНУ замену!

ПРИМЕР для "дополнить абзацем десятым пункта 17.2" (если нет других замен):
Если последний абзац пункта 17.2 заканчивается так: "...агента;"
То find должен быть: "...агента;" (или больше контекста, например последние 30-50 символов абзаца)
А replace должен быть: "...агента;\nВ непрерывный срок нахождения в собственности налогоплательщика ценных бумаг, указанных в абзаце первом настоящего пункта, включается срок, в течение которого такие ценные бумаги выбыли из собственности налогоплательщика по договору займа ценными бумагами с брокером и (или) по договору репо;"

ВАЖНО: Всегда добавляй новый абзац, если инструкция говорит "дополнить абзацем"!

КРИТИЧЕСКИ ВАЖНО ДЛЯ ПОИСКА ТЕКСТА:
- ВСЕГДА ищи текст в ИСХОДНОМ тексте, который указан в "Оригинальный текст"
- НЕ используй текст, который будет изменен предыдущими заменами
- Если инструкция говорит "заменить 'агента;' на 'агента.'" И "дополнить абзацем",
  то для добавления абзаца ищи текст с ИСХОДНЫМ "агента;", а не с замененным "агента."
- Если нужно добавить абзац после замены, найди конец абзаца с ИСХОДНЫМ текстом (до замены)

- Верни ТОЛЬКО JSON, без комментариев"""),
            ("user", """Оригинальный текст:
{before_text}

Инструкция правки:
{instruction}

Определи конкретные замены (JSON):""")
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "before_text": before_text,
            "instruction": instruction
        })
        
        response_text = response.content.strip()
        
        # Логируем сырой ответ от LLM
        print(f"[LLM] DEBUG: Raw response from LLM (first 500 chars): {response_text[:500]}")
        
        # Parse JSON replacements
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if match:
                    response_text = match.group(1)
            elif "```" in response_text:
                match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                if match:
                    response_text = match.group(1)
            
            replacements = json.loads(response_text)
            
            # Логируем полный JSON для отладки
            print(f"[LLM] DEBUG: Full JSON response from LLM:")
            print(f"[LLM] DEBUG: {json.dumps(replacements, ensure_ascii=False, indent=2)}")
            
            if not isinstance(replacements, list):
                print(f"[LLM] Unexpected response format, not a list")
                return before_text
            
            # Check for error
            if len(replacements) == 1 and replacements[0].get("error"):
                print(f"[LLM] Edit error: {replacements[0]['error']}")
                return f"[ОШИБКА: {replacements[0]['error']}]\n{before_text}"
            
            # Apply replacements to original text
            # Важно: применяем замены к исходному тексту последовательно,
            # но если замена не найдена в измененном тексте, пробуем найти её в исходном
            # Для замен, которые зависят от предыдущих, применяем их в обратном порядке
            after_text = before_text
            applied = 0
            failed = 0
            
            # Проверяем, содержит ли инструкция "дополнить абзацем" для специального логирования
            is_add_paragraph = "дополнить абзацем" in instruction.lower() or "дополнить" in instruction.lower()
            
            # Отслеживаем примененные замены для восстановления исходного текста
            applied_replacements = []
            
            # Применяем замены в обратном порядке, если есть зависимость
            # (если замена содержит текст из предыдущей замены, применяем её раньше)
            replacements_to_apply = list(replacements)
            
            for i, rep in enumerate(replacements_to_apply):
                find_str = rep.get("find", "")
                replace_str = rep.get("replace", "")
                
                if not find_str:
                    print(f"[LLM] WARNING: Replacement {i+1} has empty 'find' string")
                    continue
                
                # Пробуем найти в уже измененном тексте
                if find_str in after_text:
                    after_text = after_text.replace(find_str, replace_str, 1)
                    applied += 1
                    applied_replacements.append((find_str, replace_str))
                    if is_add_paragraph:
                        print(f"[LLM] ✅ Applied ADD PARAGRAPH replacement {i+1}: '{find_str[:80]}...' -> '{replace_str[:100]}...'")
                    else:
                        print(f"[LLM] Applied replacement {i+1}: '{find_str[:50]}...' -> '{replace_str[:50]}...'")
                # Если не найдено в измененном, пробуем найти в исходном тексте
                # Это важно для случаев, когда предыдущие замены изменили текст
                elif find_str in before_text:
                    # Находим позицию в исходном тексте
                    pos = before_text.find(find_str)
                    if pos != -1:
                        # Проверяем, не была ли эта часть уже изменена
                        # Сравниваем, что находится в этой позиции в измененном тексте
                        if pos < len(after_text):
                            # Если текст в этой позиции еще не изменен (совпадает с исходным), применяем замену
                            if after_text[pos:pos+len(find_str)] == find_str:
                                after_text = after_text[:pos] + replace_str + after_text[pos + len(find_str):]
                                applied += 1
                                applied_replacements.append((find_str, replace_str))
                                if is_add_paragraph:
                                    print(f"[LLM] ✅ Applied ADD PARAGRAPH replacement {i+1} (from original): '{find_str[:80]}...' -> '{replace_str[:100]}...'")
                                else:
                                    print(f"[LLM] Applied replacement {i+1} (from original): '{find_str[:50]}...' -> '{replace_str[:50]}...'")
                            else:
                                failed += 1
                                print(f"[LLM] ❌ WARNING: Text at position {pos} was already modified, skipping replacement {i+1}")
                                if is_add_paragraph:
                                    print(f"[LLM] ❌ CRITICAL: Failed to add paragraph! Text was already modified.")
                        else:
                            failed += 1
                            print(f"[LLM] ❌ WARNING: Position {pos} is out of bounds in modified text")
                    else:
                        failed += 1
                        print(f"[LLM] ❌ WARNING: Could not find text for replacement {i+1}: '{find_str[:80]}...'")
                else:
                    # Замена не найдена ни в измененном, ни в исходном тексте
                    # Возможно, она содержит текст, который был изменен предыдущими заменами
                    # Попробуем восстановить исходный текст для этой замены
                    print(f"[LLM] DEBUG: Replacement {i+1} not found. Attempting to restore find string...")
                    print(f"[LLM] DEBUG: Applied replacements so far: {len(applied_replacements)}")
                    restored_find = find_str
                    restored_any = False
                    for prev_find, prev_replace in applied_replacements:
                        # Если find_str содержит prev_replace, заменяем его обратно на prev_find
                        if prev_replace in restored_find:
                            restored_find = restored_find.replace(prev_replace, prev_find, 1)
                            restored_any = True
                            print(f"[LLM] DEBUG: Restored find string by replacing '{prev_replace[:50]}...' back to '{prev_find[:50]}...'")
                    
                    if restored_any:
                        print(f"[LLM] DEBUG: Restored find string: '{restored_find[:100]}...'")
                    else:
                        print(f"[LLM] DEBUG: Could not restore find string - no previous replacements match")
                        # Если восстановление не сработало, возможно find_str уже содержит исходный текст
                        # но он не найден из-за форматирования. Попробуем использовать исходный find_str
                        restored_find = find_str
                    
                    # Теперь пробуем найти восстановленный текст в исходном
                    if restored_find in before_text:
                        pos = before_text.find(restored_find)
                        if pos != -1:
                            # Применяем эту замену к исходному тексту
                            temp_text = before_text[:pos] + replace_str + before_text[pos + len(restored_find):]
                            
                            # Теперь применяем все предыдущие замены к temp_text в правильном порядке
                            # (от начала к концу, как они были применены)
                            for prev_find, prev_replace in applied_replacements:
                                if prev_find in temp_text:
                                    temp_text = temp_text.replace(prev_find, prev_replace, 1)
                            
                            # Обновляем after_text
                            after_text = temp_text
                            applied += 1
                            applied_replacements.append((restored_find, replace_str))
                            if is_add_paragraph:
                                print(f"[LLM] ✅ Applied ADD PARAGRAPH replacement {i+1} (restored and reapplied): '{restored_find[:80]}...' -> '{replace_str[:100]}...'")
                            else:
                                print(f"[LLM] Applied replacement {i+1} (restored and reapplied): '{restored_find[:50]}...' -> '{replace_str[:50]}...'")
                        else:
                            failed += 1
                            print(f"[LLM] ❌ WARNING: Could not find restored text in original for replacement {i+1}: '{restored_find[:80]}...'")
                    else:
                        # Попробуем альтернативный подход: если Replacement 2 не найден,
                        # но он должен добавить абзац после Replacement 1, найдем конец Replacement 1
                        print(f"[LLM] DEBUG: Checking alternative method conditions: is_add_paragraph={is_add_paragraph}, len(applied_replacements)={len(applied_replacements)}")
                        if is_add_paragraph and len(applied_replacements) > 0:
                            print(f"[LLM] DEBUG: Alternative method conditions met, attempting to insert paragraph...")
                            # Последняя примененная замена - это Replacement 1
                            last_find, last_replace = applied_replacements[-1]
                            print(f"[LLM] DEBUG: Last replacement: '{last_replace[:80]}...'")
                            print(f"[LLM] DEBUG: Searching for last_replace in after_text (length: {len(after_text)})...")
                            # Ищем конец last_replace в after_text
                            if last_replace in after_text:
                                last_pos = after_text.rfind(last_replace)
                                print(f"[LLM] DEBUG: Found last_replace at position {last_pos}")
                                if last_pos != -1:
                                    insert_pos = last_pos + len(last_replace)
                                    print(f"[LLM] DEBUG: Insert position: {insert_pos}")
                                    # Извлекаем новый абзац из replace_str
                                    # replace_str должен содержать: last_replace + "\n" + новый абзац + "\n" + остальное
                                    # Найдем новый абзац в replace_str
                                    print(f"[LLM] DEBUG: Searching for new paragraph in replace_str (length: {len(replace_str)})...")
                                    new_paragraph_start = replace_str.find("\nВ непрерывный срок")
                                    print(f"[LLM] DEBUG: New paragraph start position: {new_paragraph_start}")
                                    if new_paragraph_start != -1:
                                        # Находим конец нового абзаца (до следующего "\n" или конца строки)
                                        new_paragraph_end = replace_str.find(";\n", new_paragraph_start)
                                        if new_paragraph_end != -1:
                                            new_paragraph = replace_str[new_paragraph_start+1:new_paragraph_end+1]
                                            # Вставляем новый абзац после last_replace
                                            after_text = after_text[:insert_pos] + "\n" + new_paragraph + after_text[insert_pos:]
                                            applied += 1
                                            applied_replacements.append((find_str, replace_str))
                                            print(f"[LLM] ✅ Applied ADD PARAGRAPH replacement {i+1} (alternative method): inserted new paragraph after Replacement 1")
                                        else:
                                            failed += 1
                                            print(f"[LLM] ❌ WARNING: Could not extract new paragraph from replace_str")
                                    else:
                                        failed += 1
                                        print(f"[LLM] ❌ WARNING: Could not find new paragraph marker in replace_str")
                                else:
                                    failed += 1
                                    print(f"[LLM] ❌ WARNING: Could not find last replacement in after_text")
                            else:
                                failed += 1
                                print(f"[LLM] ❌ WARNING: Could not find last replacement in after_text for alternative method")
                        else:
                            failed += 1
                            print(f"[LLM] ❌ WARNING: Could not find text for replacement {i+1}: '{find_str[:80]}...'")
                            if is_add_paragraph:
                                print(f"[LLM] ❌ CRITICAL: Failed to add paragraph! Find string not found in text.")
                                # Попробуем найти похожий текст
                                if len(find_str) > 20:
                                    # Ищем последние 20 символов find_str в тексте
                                    short_find = find_str[-20:]
                                    if short_find in after_text or short_find in before_text:
                                        print(f"[LLM] ⚠️ Found similar text ending with '{short_find}', but full match failed")
            
            print(f"[LLM] Replacements: {applied} applied, {failed} failed out of {len(replacements)}")
            
            if applied == 0 and len(replacements) > 0:
                error_msg = f"[ОШИБКА: не удалось применить замены]"
                if "дополнить абзацем" in instruction.lower():
                    error_msg += " Не удалось добавить новый абзац. Проверьте, что пункт найден в тексте."
                return f"{error_msg}\n{before_text}"
            
            return after_text
            
        except json.JSONDecodeError as e:
            print(f"[LLM] Failed to parse JSON replacements: {e}")
            print(f"[LLM] Raw response: {response_text[:500]}")
            # Fallback: if response looks like full text (not JSON), use it directly
            if not response_text.startswith('[') and len(response_text) > 100:
                print(f"[LLM] Using raw response as full text fallback")
                return response_text
            return before_text
        except Exception as e:
            print(f"[LLM] Error applying replacements: {e}")
            return before_text
    
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
            print(f"[LLM] Processing content of {len(edits_content)} characters")
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Проанализируй текст правок и создай JSON с номерами статей как ключами. 
Для каждой статьи создай описание изменений СТРОГО в формате закона (как в тексте федерального закона о внесении изменений):

КРИТИЧЕСКИ ВАЖНО:
- Если инструкция содержит пункты, относящиеся к РАЗНЫМ подстатьям (например, пункт 17.2 и пункт 17.2-1), 
  то РАЗБЕЙ их на ОТДЕЛЬНЫЕ записи в JSON с разными ключами (например, "217-17.2" и "217-17.2-1")
- Если пункт относится к подстатье (например, "пункт 17.2-1"), используй ключ вида "номер_статьи-номер_подстатьи"
- Если все пункты относятся к одной подстатье, используй обычный ключ "номер_статьи"

Формат должен быть:
1) в пункте X.X:
а) [описание изменения а]
б) [описание изменения б]
в) дополнить [элемент] следующего содержания:
"[полный текст нового элемента]";

2) в пункте Y.Y:
а) [описание изменения]

ВАЖНО:
- Используй нумерацию: 1), 2), 3) для пунктов
- Используй буквы: а), б), в) для подпунктов
- Для замены: "слово 'старое' заменить словом 'новое'"
- Для дополнения: "дополнить абзацем десятым следующего содержания: \"[полный текст в кавычках]\""
- Сохраняй точную формулировку из исходного текста правок
- Не перефразируй, используй оригинальные формулировки
- ФОРМАТИРОВАНИЕ: каждый пункт (1), 2), 3)) должен начинаться с новой строки (\\n)
- ФОРМАТИРОВАНИЕ: каждая подпункт (а), б), в)) должен начинаться с новой строки (\\n)
- ФОРМАТИРОВАНИЕ: между пунктами (1) и 2), 2) и 3)) должен быть пустой абзац (\\n\\n - двойной перенос строки)

Пример:
{{
    "217": "1) в пункте 17.2:\\nа) в абзаце девятом слово \\"агента;\\" заменить словом \\"агента.\\";\\nб) дополнить абзацем десятым следующего содержания:\\n\\"В непрерывный срок нахождения в собственности налогоплательщика ценных бумаг, указанных в абзаце первом настоящего пункта, включается срок, в течение которого такие ценные бумаги выбыли из собственности налогоплательщика по договору займа ценными бумагами с брокером и (или) по договору репо;\\";\\n\\n2) абзац второй пункта 17.2-1 изложить в следующей редакции:\\n\\"акции, облигации российских организаций, инвестиционные паи относятся к ценным бумагам, обращающимся на организованном рынке ценных бумаг...\\";"
}}"""),
                ("user", "Проанализируй правки и структурируй по статьям в формате закона с правильным форматированием (каждый пункт с новой строки, пустой абзац между пунктами):\n\n{content}")
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
        instruction: Optional[str] = None,
        block_type: Optional[str] = None
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
        
        # Check if this is a technical edit (punctuation change, minor correction)
        def _is_technical_edit(before: str, after: str) -> bool:
            """Check if the change is purely technical (punctuation, minor corrections)"""
            if not before or not after:
                return False
            
            # Remove all punctuation and whitespace for comparison
            import re
            before_clean = re.sub(r'[^\w\s]', '', before.lower())
            after_clean = re.sub(r'[^\w\s]', '', after.lower())
            
            # If text content is the same (only punctuation differs), it's technical
            if before_clean == after_clean:
                return True
            
            # If the change is very small (few characters) and mostly punctuation
            if len(before) > 0 and len(after) > 0:
                diff_ratio = abs(len(before) - len(after)) / max(len(before), len(after))
                if diff_ratio < 0.1:  # Less than 10% difference
                    # Check if change is mostly punctuation
                    before_punct = len(re.findall(r'[^\w\s]', before))
                    after_punct = len(re.findall(r'[^\w\s]', after))
                    if abs(before_punct - after_punct) > 0:
                        return True
            
            return False
        
        is_technical = _is_technical_edit(before_text or "", after_text or "")
        
        # Debug log for diagnostics
        try:
            print(
                f"[ExportSummary] {article_label}: before_len={len(before_text or '')}, after_len={len(after_text or '')}, "
                f"changed_blocks={blocks}, instr_len={len(instruction or '')}, is_technical={is_technical}, block_type={block_type}"
            )
            print(f"[ExportSummary] BEFORE_EXCERPT: {before_short[:400]!r}")
            print(f"[ExportSummary] AFTER_EXCERPT: {after_short[:400]!r}")
            if instruction_short:
                print(f"[ExportSummary] INSTRUCTION: {instruction_short[:300]!r}")
        except Exception:
            pass
        
        # Build focused instruction for this specific block
        focused_instruction = instruction_short
        if block_type == "insert" and instruction_short:
            # For insert blocks, focus on "дополнить абзацем" part
            import re
            insert_match = re.search(r'дополнить\s+абзац[ем]?\s+\w+.*?(?=\.|$|;|в\s+пункте|в\s+абзаце)', instruction_short, re.IGNORECASE | re.DOTALL)
            if insert_match:
                focused_instruction = insert_match.group(0).strip()
        elif block_type == "replace" and instruction_short:
            # For replace blocks, focus on the specific replacement mentioned
            import re
            replace_match = re.search(r'(?:заменить|изменить|исправить).*?(?=\.|$|;|дополнить|в\s+пункте|в\s+абзаце)', instruction_short, re.IGNORECASE | re.DOTALL)
            if replace_match:
                focused_instruction = replace_match.group(0).strip()
        
        # Build system prompt based on block type
        if block_type == "insert":
            system_prompt = """Ты выступаешь как юрист‑редактор. 
Сформулируй краткий комментарий (1–2 коротких предложения) о сути нового абзаца.
ВАЖНО: Комментируй ТОЛЬКО новый абзац, указанный в "Стало". НЕ упоминай другие изменения из инструкции.
Начинай комментарий с "Внесен абзац, уточняющий, что..." или "Внесен абзац, устанавливающий, что..." (в зависимости от содержания).
Говори по‑делу, без Markdown и без списков.
Язык ответа — русский."""
        elif block_type == "delete":
            system_prompt = """Ты выступаешь как юрист‑редактор. 
Сформулируй краткий комментарий (1–2 коротких предложения) о сути удалённого текста.
ВАЖНО: Комментируй ТОЛЬКО удалённый текст, указанный в "Было". НЕ упоминай другие изменения из инструкции.
Говори по‑делу, без Markdown и без списков. Не используй вводные фразы вроде "Внесена правка".
Язык ответа — русский."""
        else:  # replace
            system_prompt = """Ты выступаешь как юрист‑редактор. 
Сформулируй краткий комментарий (1–2 коротких предложения) о сути внесённой правки.
ВАЖНО: Комментируй ТОЛЬКО конкретное изменение, указанное в "Было" и "Стало". НЕ упоминай другие изменения из инструкции.
Если изменение техническое (замена знаков препинания, исправление опечаток), используй термин "техническая правка", а не "исправлена опечатка".
Говори по‑делу, без Markdown и без списков. Не используй вводные фразы вроде "Внесена правка".
Язык ответа — русский."""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", """Контекст: {article_label}
Тип изменения: {block_type}

Инструкция (только для контекста, комментируй ТОЛЬКО конкретное изменение ниже):
{focused_instruction}

Было:
{before}

Стало:
{after}

Дай короткий комментарий (1–2 предложения) ТОЛЬКО об этом конкретном изменении:""")
        ])
        
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({
                "article_label": article_label,
                "block_type": block_type or "изменение",
                "focused_instruction": focused_instruction or "—",
                "before": before_short,
                "after": after_short
            })
            summary = (response.content or "").strip()
            # Ensure the comment is compact
            if len(summary) > 400:
                summary = summary[:400].rstrip() + " …"
            # Safety: strip accidental code fences or formatting
            summary = summary.replace("```", "").strip()
            
            # Replace "исправлена опечатка" with "техническая правка" for technical edits
            if is_technical:
                summary = re.sub(r'исправлена\s+опечатка', 'техническая правка', summary, flags=re.IGNORECASE)
                summary = re.sub(r'исправление\s+опечатки', 'техническая правка', summary, flags=re.IGNORECASE)
            
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
                # Сформируем понятный комментарий на основе ключевых изменений
                key_after = after_short.splitlines()
                key_snippet = ""
                for line in key_after:
                    if len(line.strip()) > 0:
                        key_snippet = line.strip()
                        break
                
                # Пытаемся извлечь смысл из изменений
                if is_technical:
                    rule_based = "Техническая правка."
                elif focused_instruction and len(focused_instruction) > 10:
                    # Используем сфокусированную инструкцию как основу для комментария
                    rule_based = focused_instruction[:300].strip()
                    if not rule_based.endswith(('.', '!', '?')):
                        rule_based += "."
                elif instruction_short and len(instruction_short) > 10:
                    # Используем инструкцию как основу для комментария
                    rule_based = instruction_short[:300].strip()
                    if not rule_based.endswith(('.', '!', '?')):
                        rule_based += "."
                elif key_snippet:
                    # Используем ключевой фрагмент нового текста
                    rule_based = f"Внесены изменения в текст статьи. {key_snippet[:200]}"
                else:
                    rule_based = "Внесены изменения в текст статьи."
                
                try:
                    print(f"[ExportSummary] OVERRIDDEN_SUMMARY: {rule_based!r}")
                except Exception:
                    pass
                return rule_based
            return summary or "Краткое описание изменения недоступно"
        except Exception as e:
            # Fall back to a meaningful comment if LLM fails
            # Try to use instruction first, then key snippet from changes
            if instruction_short and len(instruction_short) > 10:
                return instruction_short[:300].strip()
            
            # Extract meaningful snippet from after text
            if stats.get("changed_blocks", 0) > 0:
                key_after = after_short.splitlines()
                key_snippet = ""
                for line in key_after:
                    if len(line.strip()) > 0:
                        key_snippet = line.strip()
                        break
                if key_snippet:
                    return f"Внесены изменения в текст статьи. {key_snippet[:250]}"
            
            return "Внесены изменения в текст статьи. Подробности см. в колонках 'Было' и 'Стало'."

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
