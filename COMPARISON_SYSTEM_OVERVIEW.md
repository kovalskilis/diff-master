# Legal Diff — описание системы сравнения документов

## Архитектура (в 3–4 шага)

1. **Импорт базового документа**
   - Endpoint: `POST /api/import`
   - Файл (.docx/.txt) парсится в статьи и сохраняется в БД как:
     - `BaseDocument` — “контейнер” документа
     - `Article` — набор статей (`article_number`, `title`, `content`)

2. **Загрузка файла правок (workspace)**
   - Endpoint: `POST /api/workspace/file`
   - Сохраняется `WorkspaceFile` с текстом правок в `raw_payload_text`.

3. **Phase 1 — сопоставление правок со статьями (matcher)**
   - Celery task: `backend/app/worker/tasks.py::phase1_find_targets`
   - Логика:
     - LLM (или парсер) группирует правки по статьям → получается словарь `{article_number -> instruction_text}`
     - На каждую статью создаётся `EditTarget`:
       - если статья найдена → `article_id` заполнен, статус `pending`
       - если статья не найдена → статус `review` (нужно ручное подтверждение)

4. **Phase 2 — применение правок + подготовка данных для diff**
   - Celery task: `backend/app/worker/tasks.py::phase2_apply_edits`
   - Логика:
     - Для каждого `EditTarget` берётся текущий текст статьи (`Article.content`) как `before_text`
     - LLM применяет инструкцию и возвращает `after_text`
     - Сохраняется `PatchedFragment(before_text, after_text, ...)`
   - Diff строится позже из `before_text/after_text`.

## Где находится “алгоритм сравнения”

В проекте “сравнение” — это не один `compare_documents(doc1, doc2)`, а связка:

- **Сопоставление правок с сущностями документа (matcher)**:
  - `backend/app/worker/tasks.py::phase1_find_targets`
  - использует `LLMService.parse_edits_by_articles_sync(...)` (группировка правок по статьям)

- **Получение пары “до/после” (основа для сравнения)**:
  - `backend/app/worker/tasks.py::phase2_apply_edits`
  - использует `LLMService.apply_edit_instruction(before_text, instruction)`

- **Генерация diff (визуализация сравнения)**:
  - `backend/app/api/diff.py`
  - использует `difflib.HtmlDiff()` (HTML-таблица “Было/Стало”) и `difflib.unified_diff()` (текстовый diff)

## Основные сущности данных (БД)

- **`BaseDocument`**
  - базовый документ (имя, тип источника, время импорта)
  - связь 1→N с `Article`, `Snapshot`, `WorkspaceFile`

- **`Article`**
  - статья документа
  - ключевые поля: `article_number`, `title`, `content`

- **`WorkspaceFile`**
  - файл/текст правок, загружаемый пользователем
  - ключевое поле: `raw_payload_text` (из него Phase 1 делает цели правок)

- **`EditTarget`**
  - цель правки: какая инструкция к какой статье относится
  - ключевые поля:
    - `instruction_text` (инструкция правки)
    - `article_id` (если сопоставили со статьёй)
    - `status` (`pending/review/completed`)

- **`PatchedFragment`**
  - результат применения правки: “до/после”
  - ключевые поля:
    - `before_text`
    - `after_text`
    - `change_type`
    - `metadata_json` (например, исходная инструкция)

## Ядро: “функция сравнения” (псевдокод)

Ниже — упрощённая форма того, что делает система. По смыслу это “compare” между исходным текстом статьи и изменённым текстом после применения правки.

```python
def compare_documents(base_document_id: int, workspace_file_id: int) -> list[dict]:
    # Шаг 1: загрузить статьи базового документа (исходные тексты)
    articles = load_articles(base_document_id)

    # Шаг 2: Phase 1 — получить цели правок (EditTarget) по файлу правок
    targets = phase1_find_targets(workspace_file_id)

    # Шаг 3: Phase 2 — для каждой цели получить before/after и сохранить PatchedFragment
    fragments = []
    for t in targets:
        before_text = articles[t.article_number].content               # исходник
        after_text = apply_edit_instruction(before_text, t.instruction) # преобразование (LLM)
        fragments.append({"before": before_text, "after": after_text, "article": t.article_number})

    # Шаг 4: сгенерировать diff (HTML или unified) для вывода
    diff_result = [make_diff(f["before"], f["after"]) for f in fragments]
    return diff_result
```

## Реальные места в коде (high-signal)

- Phase 1 (matcher / группировка правок по статьям):  
  - `backend/app/worker/tasks.py::phase1_find_targets`

- Phase 2 (создание before/after):  
  - `backend/app/worker/tasks.py::phase2_apply_edits`

- Diff (HTML-таблица “Было/Стало”):  
  - `backend/app/api/diff.py` → `difflib.HtmlDiff().make_table(...)`

## Важное замечание про `POST /api/documents/compare`

В текущей версии проекта отдельного endpoint `POST /api/documents/compare` **нет**.
Сравнение реализовано через пайплайн:
`/api/import` → `/api/workspace/file` → `/api/edits/apply/phase1` → `/api/edits/apply/phase2` → `/api/diff`.

Если нужен именно единый endpoint “compare”, его можно добавить как “оркестратор”, который:
- принимает `document_id` + `workspace_file_id` (или `snapshot_id`)
- при необходимости запускает Phase 1/2
- возвращает агрегированный diff.

