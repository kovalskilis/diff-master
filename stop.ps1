# Скрипт остановки проекта

Write-Host "🛑 Остановка Legal Diff проекта..." -ForegroundColor Yellow

docker-compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Проект остановлен" -ForegroundColor Green
} else {
    Write-Host "❌ Ошибка при остановке проекта" -ForegroundColor Red
}
