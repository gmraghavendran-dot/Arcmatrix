param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating ArcMatrix virtual environment..." -ForegroundColor Cyan
& $Python -m venv .\venv312

Write-Host "Activating environment..." -ForegroundColor Cyan
& .\venv312\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "Installing ArcMatrix dependencies..." -ForegroundColor Cyan
python -m pip install -r .\requirements.txt

Write-Host ""
Write-Host "ArcMatrix venv is ready." -ForegroundColor Green
Write-Host "Activate later with:" -ForegroundColor Yellow
Write-Host ".\venv312\Scripts\Activate.ps1"
