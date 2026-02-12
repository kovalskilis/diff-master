# Legal Diff - Умная обработка юридических документов

Full-stack приложение для интеллектуальной обработки правок в юридических документах с использованием LLM (DeepSeek/OpenAI).

## 🎯 Основные возможности

- **Умная обработка правок** - LLM автоматически находит адреса правок в документе
- **Ручная проверка** - Review Stage позволяет пользователю проверить и скорректировать найденные цели
- **Визуализация изменений** - diff-viewer с подсветкой изменений (в стиле Git)
- **История версий** - полная история изменений документа
- **Экспорт в Excel** - генерация отчетов по шаблону с колонками "Было/Стало"
- **Полнотекстовый поиск** - FTS на PostgreSQL для русского языка
- **Премиальный UI** - минималистичный дизайн, плавные анимации

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- DeepSeek API ключ (или OpenAI API ключ)

### Установка и запуск (Docker - Рекомендуется)

1. **Клонируйте репозиторий**
```bash
git clone <repository-url>
cd diff-master2
```

2. **Создайте файл `backend/.env`** с настройками:
```env
DATABASE_URL=postgresql://legal_diff_user:dev123@db:5432/legal_diff
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SECRET_KEY=sdkljfhdlskfjkl3489r79fjisfklj0342
OPENAI_API_KEY=sk-your-openai-key-here
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

3. **Запустите проект одной командой:**

**Windows (PowerShell):**
```powershell
.\start.ps1
```

**Linux/Mac:**
```bash
docker-compose up -d --build
```

4. **Откройте приложение**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Полезные команды:**
```bash
# Просмотр логов
docker-compose logs -f

# Остановка проекта
docker-compose down

# Перезапуск
docker-compose restart
```

### Локальная разработка (без Docker)

Если вы хотите запускать сервисы локально без Docker:

1. **Запустите инфраструктуру (PostgreSQL и Redis)**
```bash
docker compose -f docker-compose.dev.yml up -d
```

2. **Настройте Backend** - создайте `backend/.env`:
```env
DATABASE_URL=postgresql://legal_diff_user:dev123@localhost:5432/legal_diff
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SECRET_KEY=sdkljfhdlskfjkl3489r79fjisfklj0342
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

3. **Запустите Backend** (терминал 1):
```bash
cd backend
python -m uvicorn app.app:app --reload --host 0.0.0.0 --port 8000
```

4. **Запустите Celery Worker** (терминал 2):
```bash
cd backend
celery -A app.worker.celery_app worker --loglevel=info
```

5. **Запустите Frontend** (терминал 3):
```bash
cd frontend
npm run dev
```

## 📖 Основное использование

### 1. Регистрация
- Откройте http://localhost:5173
- Нажмите "Нет аккаунта? Зарегистрироваться"
- Введите email и пароль

### 2. Импорт базового документа
- Нажмите "+ Новый документ"
- Загрузите .docx или .txt файл с базовым документом

### 3. Загрузка правок
- Откройте документ
- Нажмите "Найти цели" (Phase 1)
- Дождитесь завершения анализа LLM

### 4. Проверка и редактирование
- Проверьте найденные соответствия
- Если нужно, измените цель правки
- Используйте поиск для выбора правильного раздела

### 5. Применение правок
- Нажмите "Применить правки" (Phase 2)
- LLM применит правки к документу
- Подождите завершения (1-2 минуты)

### 6. Просмотр изменений
- Просмотрите изменения в diff-viewer
- Нажмите "Зафиксировать версию" для сохранения
- Экспортируйте отчет в Excel при необходимости

## 📊 API Документация

После запуска приложения документация доступна по адресу:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Основные эндпоинты

**Аутентификация**
- `POST /auth/register` - Регистрация
- `POST /auth/jwt/login` - Вход
- `GET /users/me` - Текущий пользователь

**Документы**
- `GET /api/documents` - Список документов
- `POST /api/documents` - Импорт документа
- `DELETE /api/documents/{id}` - Удалить документ

**Правки**
- `POST /api/workspace/file` - Загрузить файл правок
- `POST /api/edits/phase1/{workspace_file_id}` - Запустить поиск целей
- `GET /api/edits/targets/{workspace_file_id}` - Получить цели
- `PUT /api/edits/target/{target_id}` - Обновить цель
- `POST /api/edits/phase2/{workspace_file_id}` - Применить правки

**Diff и версии**
- `GET /api/diff` - Получить изменения
- `GET /api/versions` - История версий
- `POST /api/versions/commit` - Зафиксировать версию

**Экспорт**
- `POST /api/export/excel` - Экспорт в Excel

## 🛠️ Управление окружением

### Остановка
```bash
# Остановить Backend/Frontend (Ctrl+C в терминалах)
# Остановить инфраструктуру
docker compose -f docker-compose.dev.yml down
```

### Очистка данных
```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
```

### Просмотр логов
```bash
docker compose -f docker-compose.dev.yml logs -f
```

## 🐛 Устранение проблем

### Backend не запускается
```bash
# Проверьте логи
docker compose -f docker-compose.dev.yml logs db

# Проверьте подключение к БД
docker exec -it legal-diff-db-dev psql -U legal_diff_user -d legal_diff

# Проверьте .env файл
cat backend/.env
```

### Celery не работает
```bash
# Проверьте Redis
docker exec -it legal-diff-redis-dev redis-cli ping

# Перезапустите Celery
```

### Порты заняты
Если порты 5432 или 6379 заняты:
```bash
# Остановите локальные сервисы
sudo systemctl stop postgresql
sudo systemctl stop redis-server

# Или измените порты в docker-compose.dev.yml
```

## 📝 Что дальше?

- Для разработчиков: см. [DEVELOPER_README.md](DEVELOPER_README.md)
- Для быстрого старта: см. [QUICK_START.md](QUICK_START.md)
- Для структуры проекта: см. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## 🔐 Безопасность

⚠️ **Внимание:** Для production использования:
1. Измените `SECRET_KEY` на случайную строку
2. Используйте сильные пароли для PostgreSQL
3. Настройте SSL/TLS для всех соединений
4. Настройте резервное копирование базы данных
5. Ограничьте CORS origins только вашим доменом
6. Настройте rate limiting для API

## 📄 License

MIT License

---

Приятной работы! 🎉
