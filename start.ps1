Write-Host "Запуск ветки future-1"
docker compose down
docker compose up --build -d
Write-Host "Ожидайте 45 секунд..."
Start-Sleep -Seconds 45
Write-Host "Готово!"
Write-Host "API: http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
