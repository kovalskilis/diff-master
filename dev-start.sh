#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  🚀 Legal Diff - Development Mode (Hybrid)${NC}"
echo -e "${BLUE}  📦 Infrastructure: Docker | 💻 Code: Local${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

# Проверка Docker
echo -e "${YELLOW}[1/5] Проверка Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker не установлен!${NC}"
    echo -e "  Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker установлен${NC}"

# Запуск инфраструктуры в Docker
echo -e "\n${YELLOW}[2/5] Запуск PostgreSQL и Redis в Docker...${NC}"
docker compose -f docker-compose.dev.yml up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PostgreSQL и Redis запущены в Docker${NC}"
    echo -e "${CYAN}  - PostgreSQL: localhost:5432${NC}"
    echo -e "${CYAN}  - Redis: localhost:6379${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Docker контейнеры${NC}"
    exit 1
fi

# Ждем готовности PostgreSQL
echo -e "\n${YELLOW}[3/5] Ожидание готовности PostgreSQL...${NC}"
for i in {1..30}; do
    if docker exec legal-diff-db-dev pg_isready -U legal_diff_user -d legal_diff &> /dev/null; then
        echo -e "${GREEN}✓ PostgreSQL готов${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Проверка виртуального окружения Backend
echo -e "\n${YELLOW}[4/5] Проверка Backend venv...${NC}"
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}⚠ Виртуальное окружение не найдено. Создаю...${NC}"
    cd backend
    python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip -q
    echo "Установка зависимостей (это займет 1-2 минуты)..."
    pip install -r requirements.txt -q
    cd ..
    echo -e "${GREEN}✓ Виртуальное окружение создано и зависимости установлены${NC}"
else
    echo -e "${GREEN}✓ Виртуальное окружение существует${NC}"
fi

# Копирование .env файлов
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠ Создаю backend/.env из шаблона...${NC}"
    cp backend/.env.local backend/.env
    echo -e "${RED}⚠ ВАЖНО: Укажите свой OPENAI_API_KEY в backend/.env${NC}"
fi

# Проверка node_modules Frontend
echo -e "\n${YELLOW}[5/5] Проверка Frontend зависимостей...${NC}"
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠ Frontend зависимости не установлены. Устанавливаю...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓ Frontend зависимости установлены${NC}"
else
    echo -e "${GREEN}✓ Frontend зависимости установлены${NC}"
fi

# Копирование .env файлов
if [ ! -f "frontend/.env" ]; then
    echo -e "${YELLOW}⚠ Создаю frontend/.env из шаблона...${NC}"
    cp frontend/.env.local frontend/.env
fi

# Инструкции
echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  ✅ Инфраструктура запущена в Docker!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

echo -e "${CYAN}📦 Docker контейнеры:${NC}"
echo -e "  - PostgreSQL: localhost:5432 (legal-diff-db-dev)"
echo -e "  - Redis: localhost:6379 (legal-diff-redis-dev)"

echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  📋 Теперь откройте 2 терминала и выполните:${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

echo -e "${GREEN}📍 Терминал 1 - Backend (FastAPI + Celery):${NC}"
echo -e "   cd $(pwd)/backend"
echo -e "   source venv/bin/activate"
echo -e "   ${CYAN}# Запустите Backend API:${NC}"
echo -e "   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo -e "   ${CYAN}# В другой вкладке запустите Celery Worker:${NC}"
echo -e "   celery -A app.worker.celery_app worker --loglevel=info"

echo -e "\n${GREEN}📍 Терминал 2 - Frontend (React):${NC}"
echo -e "   cd $(pwd)/frontend"
echo -e "   npm run dev"

echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  🌐 После запуска будет доступно:${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

echo -e "${GREEN}Frontend:${NC}  http://localhost:5173"
echo -e "${GREEN}Backend:${NC}   http://localhost:8000"
echo -e "${GREEN}API Docs:${NC}  http://localhost:8000/docs"

echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  🛠️  Полезные команды:${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

echo -e "${CYAN}# Остановить инфраструктуру:${NC}"
echo -e "  docker compose -f docker-compose.dev.yml down"

echo -e "\n${CYAN}# Посмотреть логи PostgreSQL:${NC}"
echo -e "  docker logs legal-diff-db-dev -f"

echo -e "\n${CYAN}# Подключиться к PostgreSQL:${NC}"
echo -e "  docker exec -it legal-diff-db-dev psql -U legal_diff_user -d legal_diff"

echo -e "\n${CYAN}# Сбросить базу данных:${NC}"
echo -e "  docker compose -f docker-compose.dev.yml down -v"
echo -e "  docker compose -f docker-compose.dev.yml up -d"

echo -e "\n${YELLOW}💡 Tip: Backend и Frontend с hot-reload, инфраструктура изолирована!${NC}\n"

