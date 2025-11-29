<#
.SYNOPSIS
    FamilyGuard - Monitoring Stack Launcher
    A simple script to start the monitoring stack
#>

# Configuration
$dockerComposeFile = "docker-compose.monitoring.yml"

# Console Colors
$colors = @{
    Header = "Cyan"
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "White"
}

# Helper Functions
function Write-Header { param($t) Write-Host "`n=== $t ===" -ForegroundColor $colors.Header }
function Write-Success { param($t) Write-Host "[✓] $t" -ForegroundColor $colors.Success }
function Write-Info { param($t) Write-Host "[i] $t" -ForegroundColor $colors.Info }
function Write-Warning { param($t) Write-Host "[!] $t" -ForegroundColor $colors.Warning }
function Write-Error { param($t) Write-Host "[X] $t" -ForegroundColor $colors.Error }

# Check Docker
function Test-DockerRunning {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        Write-Error "Docker is not running. Please start Docker Desktop first."
        return $false
    }
}

# Start Docker containers
function Start-DockerContainers {
    Write-Header "Starting Monitoring Stack"
    
    if (-not (Test-Path $dockerComposeFile)) {
        Write-Error "Docker Compose file not found: $dockerComposeFile"
        return $false
    }
    
    try {
        Write-Info "Pulling latest images..."
        docker-compose -f $dockerComposeFile pull
        
        Write-Info "Starting containers (this may take a few minutes)..."
        docker-compose -f $dockerComposeFile up -d
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to start containers"
        }
        
        Write-Info "Waiting for services to initialize..."
        Start-Sleep -Seconds 10
        Write-Success "Monitoring stack started successfully"
        return $true
    }
    catch {
        Write-Error "Failed to start monitoring stack: $_"
        return $false
    }
}

# Show dashboard information
function Show-DashboardInfo {
    Write-Header "FamilyGuard Monitoring Dashboard"
    
    Write-Host "`nGrafana Dashboard: http://localhost:3000" -ForegroundColor $colors.Info
    Write-Host "Username: admin" -ForegroundColor $colors.Info
    Write-Host "Password: admin" -ForegroundColor $colors.Info
    Write-Host "`nOther Services:" -ForegroundColor $colors.Info
    Write-Host "- Prometheus:    http://localhost:9090" -ForegroundColor $colors.Info
    Write-Host "- Loki (Logs):   http://localhost:3100" -ForegroundColor $colors.Info
    Write-Host "- Alertmanager:  http://localhost:9093" -ForegroundColor $colors.Info
}

# Main Execution
Clear-Host
Write-Host "`n   _____           _ _   _   _____                     _ " -ForegroundColor Cyan
Write-Host "  |  ___|__   ___ | | | | |_|_   _| __ __ _ _ __  _ __ | |_   _ " -ForegroundColor Cyan
Write-Host "  | |_ / _ \ / _ \| | | | | | | || '__/ _\ | '_ \| '_ \| | | | |" -ForegroundColor Cyan
Write-Host "  |  _| (_) | (_) | | | |_| | | || | | (_| | | | | | | | | |_| |" -ForegroundColor Cyan
Write-Host "  |_|  \___/ \___/|_|_|\__, | |_||_|  \__,_|_| |_|_| |_|_|\__, |" -ForegroundColor Cyan
Write-Host "                       |___/                               |___/ " -ForegroundColor Cyan
Write-Host "`n                     Monitoring Stack Launcher v1.0" -ForegroundColor Cyan
Write-Host "`n"

# Check if Docker is running
if (-not (Test-DockerRunning)) {
    exit 1
}

# Start containers
if (Start-DockerContainers) {
    Show-DashboardInfo
    
    $openBrowser = Read-Host "`nWould you like to open the dashboard in your default browser? (y/n)"
    if ($openBrowser -eq 'y') {
        try {
            Start-Process "http://localhost:3000"
        }
        catch {
            Write-Warning "Could not open browser automatically. Please visit http://localhost:3000"
        }
    }
    
    Write-Host "`nTo stop the monitoring stack, run: docker-compose -f $dockerComposeFile down" -ForegroundColor $colors.Info
}

# Keep the window open
Write-Host "`nPress any key to exit..." -NoNewline
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
```__