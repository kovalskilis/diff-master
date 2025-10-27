# ⚡ Быстрый старт за 5 минут

## 1. Запустите инфраструктуру (Docker)

```bash
docker compose -f docker-compose.dev.yml up -d
```

## 2. Настройте Backend

```bash
cd backend
source venv/bin/activate  # или: python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Создайте .env
cat > .env << 'EOF'
DATABASE_URL=postgresql://legal_diff_user:dev123@localhost:5432/legal_diff
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SECRET_KEY=dev-secret
OPENAI_API_KEY=sk-your-key-here
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
EOF

# Примените миграции
alembic upgrade head
```

## 3. Запустите Backend

Терминал 1 (API):
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Терминал 2 (Celery):
```bash
cd backend
source venv/bin/activate
celery -A app.worker.celery_app worker --loglevel=info
```

## 4. Запустите Frontend

Терминал 3:
```bash
cd frontend
npm install
npm run dev
```

## 5. Откройте в браузере

- Приложение: http://localhost:5173
- API Docs: http://localhost:8000/docs

## 🎉 Готово!

Для подробной документации см.:
- [README.md](README.md) - общий обзор
- [DEVELOPER_README.md](DEVELOPER_README.md) - для разработчиков
