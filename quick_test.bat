@echo off
echo ========================================
echo Quick Backend API Test (No Auth)
echo ========================================
echo.

echo Testing health endpoint...
curl -s http://localhost:8000/api/health
echo.
echo.

echo Testing documents list...
curl -s http://localhost:8000/api/documents
echo.
echo.

echo Testing search...
curl -s "http://localhost:8000/api/search?q=test&limit=5"
echo.
echo.

echo ========================================
echo If you see JSON responses (not 401/403), test passed!
echo ========================================
pause
