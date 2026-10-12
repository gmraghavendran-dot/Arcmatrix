param(
    [int]$Port = 8000
)

if (-not (Test-Path ".\venv312\Scripts\python.exe")) {
    Write-Host "Creating Python 3.12 virtual environment..."
    python -m venv venv312
}

Write-Host "Installing/updating dependencies..."
.\venv312\Scripts\python.exe -m pip install --upgrade pip
.\venv312\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".\.env")) {
    Write-Host ""
    Write-Host "Missing .env. Copy .env.example to .env and set DB_PASSWORD first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting ArcMatrix on http://127.0.0.1:$Port ..."
.\venv312\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port --reload
