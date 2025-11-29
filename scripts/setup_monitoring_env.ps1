# Monitoring Environment Setup Script
# Run this script to set up environment variables for alerting

# Stop on any error
$ErrorActionPreference = "Stop"

# Load environment from .env file if it exists
$envFile = "$PSScriptRoot\..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        if ($name -and $value) {
            [System.Environment]::SetEnvironmentVariable($name, $value, [System.EnvironmentVariableTarget]::Process)
            Write-Host "Set $name"
        }
    }
}

# Required environment variables for alerting
$requiredVars = @(
    "OPSGENIE_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "SLACK_WEBHOOK_URL",
    "PAGERDUTY_INTEGRATION_KEY",
    "TEAMS_WEBHOOK_URL"
)

# Check for missing variables
$missingVars = $requiredVars | Where-Object { -not [System.Environment]::GetEnvironmentVariable($_) }

if ($missingVars) {
    Write-Host "The following required environment variables are not set:" -ForegroundColor Red
    $missingVars | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host "`nPlease set them in your environment or create a .env file in the project root." -ForegroundColor Yellow
    
    # Create sample .env file if it doesn't exist
    if (-not (Test-Path $envFile)) {
        $sampleVars = $requiredVars | ForEach-Object { "# $_=your_value_here" }
        $sampleVars -join "`n" | Out-File -FilePath $envFile -Encoding utf8
        Write-Host "`nA sample .env file has been created at $envFile" -ForegroundColor Cyan
    }
    
    exit 1
}

# Start the monitoring stack
Write-Host "`nStarting monitoring stack..." -ForegroundColor Green
Set-Location "$PSScriptRoot\.."
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to start
Write-Host "`nWaiting for services to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# Check service status
$services = @("prometheus", "grafana", "loki", "promtail", "otel-collector")
foreach ($service in $services) {
    $status = docker-compose -f docker-compose.monitoring.yml ps $service --status running --quiet
    if ($status) {
        Write-Host "✓ $service is running" -ForegroundColor Green
    } else {
        Write-Host "✗ $service is not running" -ForegroundColor Red
    }
}

# Display access information
Write-Host "`nMonitoring Services:" -ForegroundColor Cyan
Write-Host "- Grafana:     http://localhost:3000"
Write-Host "  Username:    admin"
Write-Host "  Password:    admin"
Write-Host "- Prometheus:  http://localhost:9090"
Write-Host "- Loki:        http://localhost:3100"
Write-Host "- Alertmanager: http://localhost:9093"

Write-Host "`nTo test the alerting system, run: scripts/test_alerts.ps1" -ForegroundColor Yellow
