Write-Host "Starting Document Intelligence RAG Platform..." -ForegroundColor Cyan

docker compose up -d --build

Write-Host ""
Write-Host "Services started." -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend API docs: http://localhost:8000/docs"
Write-Host "Qdrant dashboard: http://localhost:6333/dashboard"
Write-Host ""
Write-Host "To view logs: docker compose logs -f"
Write-Host "To stop: docker compose down"