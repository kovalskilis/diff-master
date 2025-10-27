# Legal Diff - Руководство разработчика

Полное руководство по разработке и расширению функционала Legal Diff.

## 🏗️ Архитектура

### Backend

**Технологии:**
- **FastAPI** - современный асинхронный Python фреймворк
- **PostgreSQL** - база данных с поддержкой FTS
- **Celery + Redis** - асинхронная обработка LLM-задач
- **LangChain + DeepSeek** - извлечение и применение правок
- **SQLAlchemy** - ORM с async/await
- **Alembic** - миграции базы данных

**Структура:**
```
backend/app/
├── api/              # API endpoints
├── models/           # SQLAlchemy модели
├── schemas/          # Pydantic схемы
├── services/         # Бизнес-логика
├── worker/           # Celery tasks
└── utils/            # Утилиты
```

### Frontend

**Технологии:**
- **React 18 + TypeScript** - современный типизированный фронтенд
- **Tailwind CSS** - utility-first CSS фреймворк
- **Framer Motion** - плавные анимации
- **Zustand** - легковесный state management
- **React Router** - навигация
- **Vite** - сборщик и dev server
- **ReactDiffViewer** - визуализация diff

**Структура:**
```
frontend/src/
├── components/       # UI компоненты
├── pages/            # Страницы
├── services/         # API clients
├── hooks/            # React hooks
├── types/            # TypeScript типы
└── styles/           # Стили
```

### Инфраструктура

- **Docker Compose** - оркестрация PostgreSQL и Redis
- **Alembic** - миграции базы данных
- **Redis** - брокер для Celery

## 🚀 Настройка окружения разработки

### 1. Клонируйте репозиторий

```bash
git clone <repository-url>
cd diff-master
```

### 2. Запустите инфраструктуру (Docker)

```bash
docker compose -f docker-compose.dev.yml up -d
```

Это запустит PostgreSQL и Redis в Docker.

### 3. Настройте Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt

# Создайте .env файл
cat > .env << 'EOF'
DATABASE_URL=postgresql://legal_diff_user:dev123@localhost:5432/legal_diff
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-change-in-production
OPENAI_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
EOF
```

### 4. Примените миграции

```bash
alembic upgrade head
```

### 5. Запустите Backend

**Терминал 1 (API):**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Терминал 2 (Celery):**
```bash
cd backend
source venv/bin/activate
celery -A app.worker.celery_app worker --loglevel=info
```

### 6. Настройте Frontend

```bash
cd frontend
npm install

# Создайте .env
echo "VITE_API_URL=http://localhost:8000" > .env

# Запустите dev server
npm run dev
```

### 7. Откройте в браузере

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📝 Структура данных

### Модели базы данных

**BaseDocument** - базовый документ
```python
id: int
user_id: UUID
name: str
imported_at: datetime
source_type: str  # docx, txt
structure: JSONB
```

**TaxUnit** - единица налогообложения (структура документа)
```python
id: int
base_document_id: int
type: TaxUnitType  # section, chapter, article, clause, sub_clause
parent_id: int
title: str
breadcrumbs_path: str
current_version_id: int
fulltext_vector: TSVECTOR
```

**WorkspaceFile** - файл с правками
```python
id: int
base_document_id: int
user_id: UUID
filename: str
uploaded_at: datetime
content: LargeBinary
```

**EditTarget** - цель правки
```python
id: int
workspace_file_id: int
user_id: UUID
status: EditJobStatus  # pending, running, completed, failed, review
instruction_text: str
initial_tax_unit_id: int
confirmed_tax_unit_id: int
conflicts_json: JSONB
```

**PatchedFragment** - примененный фрагмент
```python
id: int
edit_target_id: int
tax_unit_id: int
user_id: UUID
before_text: str
after_text: str
change_type: ChangeType  # added, modified, deleted
```

### Workflow обработки правок

1. **Импорт документа** (`POST /api/documents`)
   - Парсинг DOCX/TXT
   - Создание иерархии TaxUnit
   - Сохранение в БД

2. **Загрузка правок** (`POST /api/workspace/file`)
   - Загрузка файла с правками
   - Сохранение в WorkspaceFile

3. **Phase 1: Поиск целей** (`POST /api/edits/phase1/{workspace_file_id}`)
   - Celery task `phase1_find_targets`
   - LLM парсит правки по статьям
   - Создаются EditTarget с instruction_text
   - Поиск соответствий в документе

4. **Review Stage** (`GET /api/edits/targets/{workspace_file_id}`)
   - Пользователь проверяет найденные цели
   - Может изменить confirmed_tax_unit_id
   - Подтверждает готовность

5. **Phase 2: Применение** (`POST /api/edits/phase2/{workspace_file_id}`)
   - Celery task `phase2_apply_edits`
   - LLM применяет правки к confirmed_tax_unit_id
   - Создаются PatchedFragment

6. **Просмотр diff** (`GET /api/diff?workspace_file_id={id}`)
   - Отображение before_text и after_text
   - Визуализация изменений

## 🔧 Разработка новых функций

### Добавление нового API endpoint

1. **Создайте endpoint в `backend/app/api/`**

```python
# backend/app/api/example.py
from fastapi import APIRouter, Depends
from models.user import User
from auth import current_active_user

router = APIRouter(prefix="/api/example", tags=["example"])

@router.get("/")
async def example_endpoint(
    user: User = Depends(current_active_user)
):
    return {"message": f"Hello {user.email}"}
```

2. **Зарегистрируйте router в `app.py`**

```python
from api.example import router as example_router
app.include_router(example_router)
```

3. **Добавьте схему в `schemas/`**

```python
# backend/app/schemas/example.py
from pydantic import BaseModel

class ExampleResponse(BaseModel):
    message: str
```

### Добавление новой модели БД

1. **Создайте модель в `models/document.py`**

```python
class ExampleModel(Base):
    __tablename__ = "example"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    data = Column(Text)
```

2. **Создайте миграцию**

```bash
cd backend
source venv/bin/activate
alembic revision --autogenerate -m "add_example_model"
alembic upgrade head
```

3. **Добавьте схему в `schemas/`**

```python
class ExampleSchema(BaseModel):
    id: int
    user_id: UUID
    data: str
    
    model_config = ConfigDict(from_attributes=True)
```

### Добавление новой Celery task

1. **Добавьте task в `worker/tasks.py`**

```python
@celery_app.task
def my_new_task(param1: str, param2: int):
    # Ваша логика
    result = do_something(param1, param2)
    return {"status": "success", "result": result}
```

2. **Вызовите task из API**

```python
@router.post("/my-endpoint")
async def my_endpoint():
    task = my_new_task.delay("value", 123)
    return {"task_id": task.id}
```

### Добавление нового UI компонента

1. **Создайте компонент в `frontend/src/components/`**

```typescript
// ExampleComponent.tsx
import { useState } from 'react';

export function ExampleComponent() {
  const [count, setCount] = useState(0);
  
  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>Increment</button>
    </div>
  );
}
```

2. **Используйте компонент в странице**

```typescript
import { ExampleComponent } from '../components/ExampleComponent';

export function MyPage() {
  return (
    <div>
      <ExampleComponent />
    </div>
  );
}
```

## 🧪 Тестирование

### Backend тесты

```bash
cd backend
source venv/bin/activate

# Установите pytest
pip install pytest pytest-asyncio

# Запустите тесты
pytest tests/
```

### Frontend тесты

```bash
cd frontend

# Unit тесты
npm run test

# E2E тесты
npm run test:e2e
```

## 🐛 Отладка

### VS Code Debugging

**Backend:**
1. Установите расширение Python
2. Создайте `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/backend/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Celery Worker",
      "type": "python",
      "request": "launch",
      "module": "celery",
      "args": ["-A", "app.worker.celery_app", "worker", "--loglevel=info"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/backend/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

3. Нажмите F5 для запуска

### Chrome DevTools для Frontend

1. Откройте http://localhost:5173
2. F12 → Sources
3. Ставьте breakpoints прямо в TypeScript коде
4. Используйте React DevTools для инспекции компонентов

## 📊 Мониторинг и логи

### Логи приложения

```bash
# Backend
tail -f backend/app.log

# Celery
celery -A app.worker.celery_app events --loglevel=info

# Frontend
# Смотрите в консоль браузера (F12)
```

### База данных

```bash
# Подключиться к PostgreSQL
docker exec -it legal-diff-db-dev psql -U legal_diff_user -d legal_diff

# Полезные запросы
SELECT * FROM base_document;
SELECT * FROM edit_target WHERE status = 'review';
SELECT COUNT(*) FROM tax_unit WHERE base_document_id = 1;
```

### Redis

```bash
# Подключиться к Redis
docker exec -it legal-diff-redis-dev redis-cli

# Просмотр задач
KEYS celery*
HGETALL celery-task-meta-{task_id}
```

## 📦 Развертывание

### Production Docker

```bash
# Соберите образы
docker compose build

# Запустите
docker compose up -d

# Проверьте статус
docker compose ps

# Просмотрите логи
docker compose logs -f
```

### Environment variables

Создайте `.env` для production:

```env
DATABASE_URL=postgresql://user:strong_password@db:5432/legal_diff
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SECRET_KEY=strong-secret-key-change-this
OPENAI_API_KEY=sk-your-key-here
DEEPSEEK_API_KEY=your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## 🤝 Полезные ссылки

- [FastAPI документация](https://fastapi.tiangolo.com/)
- [SQLAlchemy документация](https://docs.sqlalchemy.org/)
- [Celery документация](https://docs.celeryproject.org/)
- [React документация](https://react.dev/)
- [TypeScript документация](https://www.typescriptlang.org/)
- [Tailwind CSS документация](https://tailwindcss.com/)

## 📝 Checklist для коммита

- [ ] Код проходит проверки линтера
- [ ] Все тесты проходят
- [ ] Добавлены/обновлены тесты для новой функциональности
- [ ] Обновлена документация API
- [ ] Обновлены схемы баз данных (миграции)
- [ ] Не содержит отладочного кода
- [ ] Не содержит закомментированного кода
- [ ] Commit message четко описывает изменения

## 🎯 Следующие шаги

- Изучите существующий код в `backend/app/` и `frontend/src/`
- Прочитайте API документацию на http://localhost:8000/docs
- Изучите структуру проекта в [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- Начните с небольших изменений (bugfix, мелкие улучшения)
- Постепенно переходите к более крупным задачам

---

Приятной разработки! 🚀

