<#
.SYNOPSIS
    FamilyGuard - Complete Monitoring Stack Setup
.DESCRIPTION
    This script automates the setup and launch of the FamilyGuard monitoring stack.
    It handles requirements installation, port checks, and service initialization.
.NOTES
    Version: 1.0
    Author: FamilyGuard Team
    Date: 2025-11-26
#>

# Set Error Action Preference
$ErrorActionPreference = "Stop"

# Console Output Configuration
$host.UI.RawUI.WindowTitle = "FamilyGuard - Setup"
$ProgressPreference = 'SilentlyContinue'

# Configuration
$requiredPorts = @(3000, 9090, 3100, 9093)
$requiredModules = @("PSSlack", "Posh-Teams")

# Console Colors
$colors = @{
    Header = "Cyan"
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "White"
    Progress = "Gray"
}

function Write-Header {
    param($text)
    Write-Host "`n=== $text ===" -ForegroundColor $colors.Header
    Write-Host ("-" * ($text.Length + 6)) -ForegroundColor $colors.Header
}

function Write-Success {
    param($text)
    Write-Host "[✓] $text" -ForegroundColor $colors.Success
}

function Write-Info {
    param($text)
    Write-Host "[i] $text" -ForegroundColor $colors.Info
}

function Write-Warning {
    param($text)
    Write-Host "[!] $text" -ForegroundColor $colors.Warning
}

function Write-Error {
    param($text)
    Write-Host "[X] $text" -ForegroundColor $colors.Error
}

function Test-CommandExists {
    param($command)
    return $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
}

function Install-RequiredModules {
    Write-Header "Checking Required Modules"
    
    # Set up NuGet provider if needed
    if (-not (Get-PackageProvider -Name NuGet -ErrorAction SilentlyContinue)) {
        Write-Info "Installing NuGet package provider..."
        Install-PackageProvider -Name NuGet -Force -Scope CurrentUser | Out-Null
    }

    # Set up PSGallery as trusted
    if ((Get-PSRepository -Name PSGallery).InstallationPolicy -ne "Trusted") {
        Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
    }

    # Install required modules
    foreach ($module in $requiredModules) {
        if (-not (Get-Module -ListAvailable -Name $module)) {
            try {
                Write-Info "Installing $module module..."
                Install-Module -Name $module -Force -AllowClobber -Scope CurrentUser -ErrorAction Stop
                Import-Module -Name $module -Force -ErrorAction Stop
                Write-Success "Successfully installed $module"
            }
            catch {
                Write-Error "Failed to install $module`: $_"
                return $false
            }
        }
        else {
            Write-Success "$module is already installed"
        }
    }
    return $true
}

function Test-PortsAvailable {
    param($ports)
    Write-Header "Checking Port Availability"
    $inUse = @()
    
    foreach ($port in $ports) {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet
        if ($connection) {
            $process = Get-Process -Id (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue
            $processName = if ($process) { $process.ProcessName } else { "Unknown" }
            $inUse += @{Port = $port; Process = $processName}
            Write-Warning "Port $port is in use by: $processName"
        }
        else {
            Write-Success "Port $port is available"
        }
    }
    
    if ($inUse.Count -gt 0) {
        Write-Warning "Some required ports are in use. Please close these applications:"
        $inUse | ForEach-Object { Write-Host "- Port $($_.Port): $($_.Process)" -ForegroundColor $colors.Warning }
        $confirmation = Read-Host "Would you like to try to continue anyway? (y/n)"
        if ($confirmation -ne 'y') {
            return $false
        }
    }
    return $true
}

function Install-DockerIfNeeded {
    Write-Header "Checking Docker Installation"
    
    if (-not (Test-CommandExists "docker")) {
        Write-Info "Docker Desktop not found. Please install Docker Desktop from:"
        Write-Host "  https://www.docker.com/products/docker-desktop" -ForegroundColor $colors.Info
        Write-Host "  After installation, run this script again." -ForegroundColor $colors.Info
        return $false
    }
    
    # Check if Docker is running
    try {
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Docker is not running. Please start Docker Desktop and try again."
            return $false
        }
        Write-Success "Docker is installed and running"
        return $true
    }
    catch {
        Write-Error "Docker is not running. Please start Docker Desktop and try again."
        return $false
    }
}

function Start-MonitoringStack {
    Write-Header "Starting Monitoring Stack"
    
    # Check if docker-compose file exists
    $composeFile = "docker-compose.monitoring.yml"
    if (-not (Test-Path $composeFile)) {
        Write-Error "Docker Compose file not found: $composeFile"
        return $false
    }
    
    try {
        Write-Info "Starting containers... (this may take a few minutes)"
        & docker-compose -f $composeFile up -d
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to start containers"
        }
        
        Write-Success "Monitoring stack started successfully"
        return $true
    }
    catch {
        Write-Error "Failed to start monitoring stack: $_"
        return $false
    }
}

function Show-DashboardInfo {
    Write-Header "FamilyGuard Monitoring Dashboard"
    
    $dashboardInfo = @{
        "Grafana Dashboard" = "http://localhost:3000"
        "Username" = "admin"
        "Password" = "admin"
        "Prometheus" = "http://localhost:9090"
        "Loki (Logs)" = "http://localhost:3100"
        "Alertmanager" = "http://localhost:9093"
    }
    
    $maxLength = ($dashboardInfo.Keys | Measure-Object -Property Length -Maximum).Maximum + 2
    
    foreach ($key in $dashboardInfo.Keys) {
        $paddedKey = $key.PadRight($maxLength)
        Write-Host "$paddedKey: $($dashboardInfo[$key])" -ForegroundColor $colors.Info
    }
    
    Write-Host "`nTo stop the monitoring stack, run: docker-compose -f docker-compose.monitoring.yml down" -ForegroundColor $colors.Info
}

# Main Execution
Clear-Host
Write-Host "`n"
Write-Host "   _____           _ _   _   _____                     _ " -ForegroundColor Cyan
Write-Host "  |  ___|__   ___ | | | | |_|_   _| __ __ _ _ __  _ __ | |_   _ " -ForegroundColor Cyan
Write-Host "  | |_ / _ \ / _ \| | | | | | | || '__/ _` | '_ \| '_ \| | | | |" -ForegroundColor Cyan
Write-Host "  |  _| (_) | (_) | | | |_| | | || | | (_| | | | | | | | | |_| |" -ForegroundColor Cyan
Write-Host "  |_|  \___/ \___/|_|_|\__, | |_||_|  \__,_|_| |_|_| |_|_|\__, |" -ForegroundColor Cyan
Write-Host "                       |___/                               |___/ " -ForegroundColor Cyan
Write-Host "`n                     Monitoring Stack Setup v1.0" -ForegroundColor Cyan
Write-Host "`n"

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "This script requires administrator privileges to install software."
    Write-Info "Please right-click on PowerShell and select 'Run as Administrator', then run this script again."
    Write-Info "Alternatively, you can run this command in an elevated PowerShell window:"
    Write-Host "  Set-ExecutionPolicy Bypass -Scope Process -Force; .\setup.ps1" -ForegroundColor $colors.Info
    exit 1
}

# Main execution flow
try {
    # Step 1: Install required modules
    if (-not (Install-RequiredModules)) {
        exit 1
    }
    
    # Step 2: Check Docker
    if (-not (Install-DockerIfNeeded)) {
        exit 1
    }
    
    # Step 3: Check ports
    if (-not (Test-PortsAvailable -ports $requiredPorts)) {
        exit 1
    }
    
    # Step 4: Start monitoring stack
    if (-not (Start-MonitoringStack)) {
        exit 1
    }
    
    # Step 5: Show dashboard information
    Show-DashboardInfo
    
    # Step 6: Open dashboard in default browser
    $openBrowser = Read-Host "`nWould you like to open the dashboard in your default browser? (y/n)"
    if ($openBrowser -eq 'y') {
        Start-Process "http://localhost:3000"
    }
    
    Write-Host "`nSetup completed successfully!" -ForegroundColor $colors.Success
}
catch {
    Write-Error "An error occurred: $_"
    exit 1
}

# Keep the window open
Write-Host "`nPress any key to exit..." -NoNewline
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
