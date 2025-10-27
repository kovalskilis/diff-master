# 📁 Структура проекта

```
diff-master/
├── backend/                    # Backend (FastAPI + Python)
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   │   ├── documents.py  # Документы
│   │   │   ├── workspace.py  # Workspace файлы
│   │   │   ├── edits.py      # Правки
│   │   │   ├── diff.py       # Diff view
│   │   │   ├── versions.py  # Версии
│   │   │   ├── search.py    # Поиск
│   │   │   └── export.py    # Экспорт
│   │   ├── models/           # SQLAlchemy модели
│   │   │   ├── user.py
│   │   │   └── document.py
│   │   ├── schemas/          # Pydantic схемы
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   └── edit.py
│   │   ├── services/          # Бизнес-логика
│   │   │   ├── llm_service.py
│   │   │   ├── document_parser.py
│   │   │   ├── parsing.py
│   │   │   ├── audit_service.py
│   │   │   └── export_service.py
│   │   ├── worker/            # Celery tasks
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   ├── app.py            # FastAPI app
│   │   ├── auth.py           # Аутентификация
│   │   ├── config.py         # Конфигурация
│   │   └── database.py       # БД setup
│   ├── alembic/              # Миграции БД
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── frontend/                   # Frontend (React + TypeScript)
│   ├── src/
│   │   ├── components/       # UI компоненты
│   │   │   └── ui/           # Button, Card, Modal, etc.
│   │   ├── pages/            # Страницы
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── DocumentPage.tsx
│   │   │   ├── ReviewPage.tsx
│   │   │   └── DiffPage.tsx
│   │   ├── services/         # API clients
│   │   │   └── api.ts
│   │   ├── hooks/            # React hooks
│   │   ├── types/            # TypeScript типы
│   │   ├── utils/            # Утилиты
│   │   └── styles/            # Стили
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
│
├── docker-compose.yml          # Production Docker
├── docker-compose.dev.yml     # Development (только infra)
├── Makefile
├── dev-start.sh
├── README.md                  # Общая документация
├── DEVELOPER_README.md        # Документация для разработчиков
├── QUICK_START.md            # Быстрый старт
└── PROJECT_STRUCTURE.md     # Этот файл
```

## Модели базы данных

- `BaseDocument` - базовый документ
- `TaxUnit` - структура документа (иерархия)
- `WorkspaceFile` - файл с правками
- `EditTarget` - цель правки
- `PatchedFragment` - примененный фрагмент
- `Snapshot` - снимок версии
- `AuditLog` - аудит действий

## Workflow обработки

1. Импорт документа → парсинг → создание TaxUnit
2. Загрузка правок → сохранение WorkspaceFile
3. Phase 1 → LLM находит цели → EditTarget
4. Review → пользователь проверяет
5. Phase 2 → LLM применяет → PatchedFragment
6. Просмотр diff → визуализация изменений

Подробнее в [DEVELOPER_README.md](DEVELOPER_README.md)
