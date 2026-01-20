# Backend Dockerfile для diff-master
# Исправлена ошибка "libstdc++.so.6: file too short"
# Использует полный Debian образ вместо slim для избежания проблем с библиотеками

FROM python:3.11-bookworm

WORKDIR /app

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Установка системных зависимостей
# Build dependencies (для компиляции Python пакетов):
# - gcc, g++: для компиляции C расширений (lxml, bcrypt, cryptography)
# - libpq-dev: заголовки для psycopg2 (хотя используется binary, но на всякий случай)
# - libxml2-dev, libxslt1-dev: для lxml (python-docx)
# - libssl-dev: для cryptography
# Runtime dependencies:
# - libpq5: для psycopg2-binary
# - libxml2, libxslt1.1: для lxml
# - libssl3, libcrypto3: для cryptography
# - libstdc++6, libgcc-s1: для всех скомпилированных расширений
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build dependencies
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    # Runtime dependencies
    libpq5 \
    libxml2 \
    libxslt1.1 \
    libssl3 \
    libstdc++6 \
    libgcc-s1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements.txt
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Копирование кода приложения
COPY . .

# Healthcheck для Docker Compose
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
CMD curl -f http://localhost:8000/api/health || exit 1

# Команда по умолчанию
# Использует переменную PORT для Render, по умолчанию 8000
CMD ["sh", "-c", "uvicorn app.app:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]