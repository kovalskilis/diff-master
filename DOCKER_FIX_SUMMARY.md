# Исправление Dockerfile для diff-master

## Проблема
Ошибка сборки: `libstdc++.so.6: file too short`

## Анализ requirements.txt

### Пакеты, требующие компиляции C расширений:
1. **lxml** (зависимость python-docx) - требует libxml2, libxslt
2. **bcrypt** - требует компиляции C
3. **cryptography** (зависимость python-jose) - требует libssl, libcrypto
4. **openpyxl** - может требовать компиляцию

### Пакеты, требующие runtime библиотеки:
1. **psycopg2-binary** - требует libpq5 (runtime)
2. **lxml** - требует libxml2, libxslt1.1 (runtime)
3. **cryptography** - требует libssl3, libcrypto3 (runtime)
4. Все скомпилированные расширения - требуют libstdc++6, libgcc-s1

## Решение

### 1. Изменен базовый образ
- **Было**: `python:3.11-slim` (минимальный образ, может не иметь всех библиотек)
- **Стало**: `python:3.11-bookworm` (полный Debian, гарантирует наличие всех библиотек)

### 2. Добавлены необходимые системные зависимости

**Build dependencies** (для компиляции):
- `gcc`, `g++` - компиляторы C/C++
- `libpq-dev` - заголовки PostgreSQL (для psycopg2)
- `libxml2-dev`, `libxslt1-dev` - заголовки для lxml
- `libssl-dev` - заголовки для cryptography

**Runtime dependencies** (для работы):
- `libpq5` - runtime библиотека для psycopg2-binary
- `libxml2`, `libxslt1.1` - runtime для lxml
- `libssl3`, `libcrypto3` - runtime для cryptography
- `libstdc++6`, `libgcc-s1` - **критично** для всех скомпилированных расширений
- `curl` - для healthcheck

### 3. Удален postgresql-client
- **Не нужен** для runtime (только для миграций)
- Миграции можно запускать через контейнер `db` или локально

### 4. Добавлен .dockerignore
- Исключает ненужные файлы из контекста сборки
- Уменьшает размер образа
- Ускоряет сборку

## Совместимость с docker-compose.yml

✅ **Полностью совместим**:
- Использует тот же порт 8000
- Поддерживает переменную PORT для Render
- Healthcheck работает с `/api/health`
- Все переменные окружения поддерживаются

## Как использовать

### Первая сборка (после исправления):
```powershell
# Очистка старого кэша (важно!)
docker compose down -v
docker system prune -af
docker builder prune -af

# Сборка с новым Dockerfile
docker compose build --no-cache api worker

# Запуск
docker compose up -d
```

### Если ошибка повторится:
1. Убедитесь, что Docker Desktop запущен
2. Очистите кэш: `docker builder prune -af`
3. Пересоберите: `docker compose build --no-cache api worker`

## Проверка

После сборки проверьте:
```powershell
docker compose ps
docker compose logs api
```

Должны быть запущены:
- api (healthy)
- frontend
- db (healthy)
- redis
- worker

## Размер образа

- **Было** (slim): ~200-300 MB
- **Стало** (bookworm): ~400-500 MB
- **Компромисс**: Больше размер, но гарантированная стабильность

## Почему это работает

1. **Полный Debian образ** содержит все необходимые библиотеки
2. **libstdc++6 и libgcc-s1** установлены явно - это решает проблему "file too short"
3. **Все runtime зависимости** установлены до компиляции Python пакетов
4. **Кэш очищен** - старые битые слои не используются
