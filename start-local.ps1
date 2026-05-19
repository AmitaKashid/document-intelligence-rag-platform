$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendUrl = "http://localhost:5173"
$BackendDocsUrl = "http://localhost:8000/docs"
$QdrantUrl = "http://localhost:6333/dashboard"

function Run-Command {
    param (
        [string]$Command,
        [string]$ErrorMessage
    )

    Write-Host $Command -ForegroundColor DarkGray
    powershell -NoProfile -Command $Command

    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

function Wait-ForPort {
    param (
        [string]$Name,
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutSeconds = 180
    )

    $StartTime = Get-Date

    while ($true) {
        $IsOpen = Test-NetConnection `
            -ComputerName $HostName `
            -Port $Port `
            -InformationLevel Quiet `
            -WarningAction SilentlyContinue

        if ($IsOpen) {
            Write-Host "$Name is ready at ${HostName}:${Port}" -ForegroundColor Green
            return
        }

        $Elapsed = ((Get-Date) - $StartTime).TotalSeconds

        if ($Elapsed -ge $TimeoutSeconds) {
            throw "$Name did not become ready on ${HostName}:${Port} within $TimeoutSeconds seconds."
        }

        Write-Host "Waiting for $Name on ${HostName}:${Port}..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 3
    }
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Starting Document Intelligence RAG Platform" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor DarkGray
Write-Host ""

Set-Location $ProjectRoot

if (!(Test-Path (Join-Path $ProjectRoot "docker-compose.yml"))) {
    throw "docker-compose.yml not found in project root: $ProjectRoot"
}

Write-Host "[1/6] Checking Docker..." -ForegroundColor Yellow

docker version | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Open Docker Desktop first, wait until it is ready, then run .\start-local.ps1 again."
}

Write-Host "Docker is running." -ForegroundColor Green

Write-Host ""
Write-Host "[2/6] Cleaning previous Compose containers..." -ForegroundColor Yellow

docker compose down --remove-orphans

# Remove stale containers that may have been created under an older Compose project name.
$StaleContainers = docker ps -a --format "{{.ID}} {{.Names}}" | Select-String "document-rag-qdrant|document-rag-backend|document-rag-frontend"

foreach ($Container in $StaleContainers) {
    $ContainerId = ($Container.ToString().Split(" ")[0])
    Write-Host "Removing stale container: $ContainerId" -ForegroundColor DarkYellow
    docker rm -f $ContainerId | Out-Null
}

Write-Host ""
Write-Host "[3/6] Building and starting containers in background..." -ForegroundColor Yellow

docker compose up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Docker Compose failed. Showing current containers:" -ForegroundColor Red
    docker ps -a
    throw "docker compose up failed. Fix the error above and run .\start-local.ps1 again."
}

Write-Host ""
Write-Host "[4/6] Waiting for services to become reachable..." -ForegroundColor Yellow

Wait-ForPort -Name "Qdrant" -HostName "127.0.0.1" -Port 6333 -TimeoutSeconds 180
Wait-ForPort -Name "Backend" -HostName "127.0.0.1" -Port 8000 -TimeoutSeconds 240
Wait-ForPort -Name "Frontend" -HostName "127.0.0.1" -Port 5173 -TimeoutSeconds 240

Write-Host ""
Write-Host "[5/6] Opening website..." -ForegroundColor Yellow
Start-Process $FrontendUrl

Write-Host ""
Write-Host "[6/6] Application started successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Frontend:          $FrontendUrl" -ForegroundColor Cyan
Write-Host "Backend API docs:  $BackendDocsUrl" -ForegroundColor Cyan
Write-Host "Qdrant dashboard:  $QdrantUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop everything, run:" -ForegroundColor Yellow
Write-Host ".\stop-local.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To view logs, run:" -ForegroundColor Yellow
Write-Host "docker compose logs -f" -ForegroundColor White
Write-Host ""