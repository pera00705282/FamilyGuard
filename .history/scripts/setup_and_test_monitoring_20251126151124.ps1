# Monitoring Setup and Test Script
# This script automates the setup and testing of the monitoring stack

# Stop on any error
$ErrorActionPreference = "Stop"

# Function to check if a command exists
function Test-CommandExists {
    param ($command)
    $exists = $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
    return $exists
}

# Function to install required PowerShell modules
function Install-RequiredModules {
    $modules = @("PSSlack", "Posh-Teams")
    $missingModules = $modules | Where-Object { -not (Get-Module -ListAvailable -Name $_) }
    
    if ($missingModules) {
        Write-Host "Installing required PowerShell modules for current user..." -ForegroundColor Cyan
        foreach ($module in $missingModules) {
            try {
                Write-Host "Installing $module..." -NoNewline
                # Install with -Scope CurrentUser to avoid needing admin rights
                Install-Module -Name $module -Force -Scope CurrentUser -ErrorAction Stop
                # Import the module to make sure it's available in the current session
                Import-Module -Name $module -Force -ErrorAction Stop
                Write-Host " ✅" -ForegroundColor Green
            }
            catch {
                Write-Host " ❌" -ForegroundColor Red
                Write-Host "Failed to install $module`: $_" -ForegroundColor Red
                Write-Host "Trying with -AllowClobber..." -ForegroundColor Yellow
                try {
                    Install-Module -Name $module -Force -Scope CurrentUser -AllowClobber -ErrorAction Stop
                    Import-Module -Name $module -Force -ErrorAction Stop
                    Write-Host " ✅ (Installed with -AllowClobber)" -ForegroundColor Green
                }
                catch {
                    Write-Host " ❌ Failed to install with -AllowClobber: $_" -ForegroundColor Red
                    return $false
                }
            }
        }
    }
    return $true
}

# Function to check and install Docker if needed
function Install-DockerIfNeeded {
    if (-not (Test-CommandExists "docker")) {
        Write-Host "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop" -ForegroundColor Red
        return $false
    }
    
    # Check if Docker is running
    try {
        $null = docker info 2>$null
        return $true
    }
    catch {
        Write-Host "Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
        return $false
    }
}

# Function to check environment variables
function Test-EnvironmentVariables {
    $requiredVars = @(
        "OPSGENIE_API_KEY",
        "SLACK_WEBHOOK_URL",
        "TEAMS_WEBHOOK_URL",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_NUMBER"
    )
    
    $missingVars = $requiredVars | Where-Object { -not [System.Environment]::GetEnvironmentVariable($_) }
    
    if ($missingVars) {
        Write-Host "The following required environment variables are not set:" -ForegroundColor Yellow
        $missingVars | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
        
        $proceed = Read-Host "Do you want to set these variables now? (Y/N)"
        if ($proceed -eq "Y" -or $proceed -eq "y") {
            foreach ($var in $missingVars) {
                $value = Read-Host "Enter value for $var"
                [System.Environment]::SetEnvironmentVariable($var, $value, "User")
                Write-Host "Set $var" -ForegroundColor Green
            }
            # Reload environment
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            return $true
        }
        return $false
    }
    return $true
}

# Function to start the monitoring stack
function Start-MonitoringStack {
    Write-Host "`nStarting monitoring stack..." -ForegroundColor Cyan
    
    # Navigate to project root
    $projectRoot = Split-Path -Parent $PSScriptRoot
    Set-Location $projectRoot
    
    # Start the stack
    try {
        docker-compose -f docker-compose.monitoring.yml up -d
        Write-Host "Monitoring stack started successfully!" -ForegroundColor Green
        
        # Wait for services to start
        Write-Host "Waiting for services to initialize..." -NoNewline
        Start-Sleep -Seconds 10
        Write-Host " ✅" -ForegroundColor Green
        
        # Show service status
        docker-compose -f docker-compose.monitoring.yml ps
        
        return $true
    }
    catch {
        Write-Host "`nFailed to start monitoring stack:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        return $false
    }
}

# Function to test alert channels
function Test-AlertChannels {
    param (
        [switch]$SkipOpsGenie,
        [switch]$SkipSlack,
        [switch]$SkipTeams,
        [switch]$SkipSms
    )
    
    $testScriptPath = Join-Path $PSScriptRoot "test_alerts.ps1"
    
    if (-not (Test-Path $testScriptPath)) {
        Write-Host "Test script not found at $testScriptPath" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`nTesting alert channels..." -ForegroundColor Cyan
    
    # Test OpsGenie
    if (-not $SkipOpsGenie -and $env:OPSGENIE_API_KEY) {
        Write-Host "`nTesting OpsGenie..." -ForegroundColor Cyan
        & $testScriptPath -TestOpsGenie
    }
    
    # Test Slack
    if (-not $SkipSlack -and $env:SLACK_WEBHOOK_URL) {
        Write-Host "`nTesting Slack..." -ForegroundColor Cyan
        & $testScriptPath -TestSlack
    }
    
    # Test Teams
    if (-not $SkipTeams -and $env:TEAMS_WEBHOOK_URL) {
        Write-Host "`nTesting Microsoft Teams..." -ForegroundColor Cyan
        & $testScriptPath -TestTeams
    }
    
    # Test SMS
    if (-not $SkipSms -and $env:TWILIO_ACCOUNT_SID -and $env:TWILIO_AUTH_TOKEN -and $env:TWILIO_FROM_NUMBER) {
        Write-Host "`nTesting SMS..." -ForegroundColor Cyan
        & $testScriptPath -TestSms
    }
    
    Write-Host "`nAlert channel testing complete!" -ForegroundColor Green
    return $true
}

# Main execution
Write-Host "=== Trading System Monitoring Setup and Test ===" -ForegroundColor Cyan

# Check and install requirements
if (-not (Install-RequiredModules)) {
    Write-Host "Failed to install required modules. Exiting." -ForegroundColor Red
    exit 1
}

if (-not (Install-DockerIfNeeded)) {
    Write-Host "Docker is required but not available. Exiting." -ForegroundColor Red
    exit 1
}

# Check environment variables
if (-not (Test-EnvironmentVariables)) {
    Write-Host "Required environment variables are not set. Exiting." -ForegroundColor Red
    exit 1
}

# Start the monitoring stack
if (Start-MonitoringStack) {
    # Show access information
    Write-Host "`nMonitoring Services:" -ForegroundColor Green
    Write-Host "- Grafana:     http://localhost:3000"
    Write-Host "  Username:    admin"
    Write-Host "  Password:    admin"
    Write-Host "- Prometheus:  http://localhost:9090"
    Write-Host "- Loki:        http://localhost:3100"
    Write-Host "- Alertmanager: http://localhost:9093"
    
    # Test alert channels
    $testAlerts = Read-Host "`nDo you want to test alert channels? (Y/N)"
    if ($testAlerts -eq "Y" -or $testAlerts -eq "y") {
        Test-AlertChannels
    }
    
    Write-Host "`nSetup and testing complete!" -ForegroundColor Green
    Write-Host "Access the monitoring dashboards at http://localhost:3000" -ForegroundColor Cyan
}
else {
    Write-Host "Failed to start the monitoring stack. Please check the error messages above." -ForegroundColor Red
    exit 1
}
