#!/usr/bin/env pwsh
# PowerShell Deployment Helper Script for Windows
# Run this script to get deployment commands

Write-Host "================================" -ForegroundColor Cyan
Write-Host "AQ Forecast - Deployment Helper" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

function Show-Menu {
    Write-Host "Choose your deployment method:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Docker (Local)" -ForegroundColor Green
    Write-Host "2. Docker Compose (Recommended)" -ForegroundColor Green
    Write-Host "3. Local Development (Python)" -ForegroundColor Green
    Write-Host "4. Check Deployment Status" -ForegroundColor Green
    Write-Host "5. View Logs" -ForegroundColor Green
    Write-Host "6. Stop Services" -ForegroundColor Green
    Write-Host "7. Cloud Deployment Info" -ForegroundColor Green
    Write-Host "0. Exit" -ForegroundColor Red
    Write-Host ""
}

function Deploy-Docker {
    Write-Host "Building and running with Docker..." -ForegroundColor Cyan
    docker build -t aq-forecast .
    docker run -d -p 8000:8000 -v ${PWD}/state_store:/app/state_store --name aq-forecast-app aq-forecast
    Write-Host "✅ Docker container started!" -ForegroundColor Green
    Write-Host "Access at: http://localhost:8000" -ForegroundColor Yellow
}

function Deploy-DockerCompose {
    Write-Host "Starting with Docker Compose..." -ForegroundColor Cyan
    docker-compose up -d
    Write-Host "✅ Docker Compose started!" -ForegroundColor Green
    Write-Host "Access at: http://localhost:8000" -ForegroundColor Yellow
}

function Deploy-Local {
    Write-Host "Starting local development server..." -ForegroundColor Cyan
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "Starting uvicorn server..." -ForegroundColor Yellow
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
}

function Check-Status {
    Write-Host "Checking deployment status..." -ForegroundColor Cyan
    python check_deployment.py
}

function View-Logs {
    Write-Host "Choose log source:" -ForegroundColor Yellow
    Write-Host "1. Docker Compose"
    Write-Host "2. Docker Container"
    $choice = Read-Host "Enter choice"
    
    if ($choice -eq "1") {
        docker-compose logs -f
    } elseif ($choice -eq "2") {
        docker logs -f aq-forecast-app
    }
}

function Stop-Services {
    Write-Host "Stopping services..." -ForegroundColor Cyan
    docker-compose down
    docker stop aq-forecast-app 2>$null
    docker rm aq-forecast-app 2>$null
    Write-Host "✅ Services stopped!" -ForegroundColor Green
}

function Show-CloudInfo {
    Write-Host ""
    Write-Host "=== Cloud Deployment Options ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🟢 Render.com (Free):" -ForegroundColor Green
    Write-Host "   1. Push to GitHub"
    Write-Host "   2. Connect at render.com"
    Write-Host "   3. Auto-detects render.yaml"
    Write-Host ""
    Write-Host "🔵 Railway.app ($5 credit):" -ForegroundColor Blue
    Write-Host "   1. Push to GitHub"
    Write-Host "   2. Deploy at railway.app"
    Write-Host "   3. Auto-detects railway.json"
    Write-Host ""
    Write-Host "🟣 Heroku:" -ForegroundColor Magenta
    Write-Host "   heroku login"
    Write-Host "   heroku create your-app"
    Write-Host "   heroku stack:set container"
    Write-Host "   git push heroku main"
    Write-Host ""
    Write-Host "See DEPLOYMENT.md for more options!" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to continue"
}

# Main loop
while ($true) {
    Show-Menu
    $choice = Read-Host "Enter your choice"
    
    switch ($choice) {
        "1" { Deploy-Docker; break }
        "2" { Deploy-DockerCompose; break }
        "3" { Deploy-Local; break }
        "4" { Check-Status }
        "5" { View-Logs }
        "6" { Stop-Services }
        "7" { Show-CloudInfo }
        "0" { 
            Write-Host "Goodbye! 👋" -ForegroundColor Cyan
            exit 
        }
        default { 
            Write-Host "Invalid choice. Please try again." -ForegroundColor Red 
        }
    }
    
    Write-Host ""
    Read-Host "Press Enter to continue"
    Clear-Host
}
