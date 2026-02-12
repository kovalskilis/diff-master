<# 
Простой скрипт запуска проекта через Docker Compose.
Без эмодзи и нестандартных символов, чтобы избежать проблем с кодировкой.
#>

Write-Host "==== Запуск проекта Legal Diff через Docker Compose ====" -ForegroundColor Green

# Проверка наличия Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ОШИБКА: Docker не установлен или не найден в PATH" -ForegroundColor Red
    exit 1
}

# Проверка наличия docker-compose (старый синтаксис)
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "ПРЕДУПРЕЖДЕНИЕ: docker-compose не найден. Пробуем 'docker compose'." -ForegroundColor Yellow
}

# Проверка наличия backend\.env
if (-not (Test-Path "backend\.env")) {
    Write-Host "ОШИБКА: Файл backend\.env не найден." -ForegroundColor Red
    Write-Host "Создайте файл backend\.env с нужными переменными окружения и запустите скрипт снова." -ForegroundColor Yellow
    exit 1
}

Write-Host "Сборка и запуск контейнеров..." -ForegroundColor Cyan

if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    docker-compose up -d --build
} else {
    docker compose up -d --build
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Проект успешно запущен." -ForegroundColor Green
    Write-Host ""
    Write-Host "Доступные сервисы:" -ForegroundColor Cyan
    Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor White
    Write-Host "  Backend:   http://localhost:8000" -ForegroundColor White
    Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "Полезные команды:" -ForegroundColor Cyan
    Write-Host "  docker-compose logs -f    (или docker compose logs -f)" -ForegroundColor Yellow
    Write-Host "  docker-compose down       (или docker compose down)" -ForegroundColor Yellow
} else {
    Write-Host "ОШИБКА: Возникла ошибка при запуске docker-compose." -ForegroundColor Red
    exit 1
}
