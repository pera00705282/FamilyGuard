# Alert Testing Script
# This script helps test the alerting system by generating test alerts

# Check if required modules are installed
$requiredModules = @("PSSlack", "Posh-Teams")
$missingModules = $requiredModules | Where-Object { -not (Get-Module -ListAvailable -Name $_) }

if ($missingModules) {
    Write-Host "The following modules are required but not installed:" -ForegroundColor Yellow
    $missingModules | ForEach-Object { Write-Host "  - $_" }
    $install = Read-Host "Do you want to install the missing modules? (Y/N)"
    if ($install -eq "Y" -or $install -eq "y") {
        $missingModules | ForEach-Object { Install-Module -Name $_ -Force -Scope CurrentUser }
    } else {
        Write-Host "Please install the required modules and try again." -ForegroundColor Red
        exit 1
    }
}

# Import required modules
Import-Module PSSlack
Import-Module Posh-Teams

# Test OpsGenie Alert
function Test-OpsGenieAlert {
    param (
        [string]$apiKey = $env:OPSGENIE_API_KEY,
        [string]$message = "Test Alert from Trading System",
        [string]$description = "This is a test alert to verify OpsGenie integration.",
        [string]$priority = "P3"
    )
    
    if (-not $apiKey) {
        Write-Host "OpsGenie API key not found. Please set OPSGENIE_API_KEY environment variable." -ForegroundColor Red
        return
    }
    
    $headers = @{
        "Authorization" = "GenieKey $apiKey"
        "Content-Type" = "application/json"
    }
    
    $body = @{
        message = $message
        description = $description
        priority = $priority
        tags = @("test", "trading", "alert")
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "https://api.opsgenie.com/v2/alerts" -Method Post -Headers $headers -Body $body
        Write-Host "✅ OpsGenie test alert sent successfully!" -ForegroundColor Green
        Write-Host "   Alert ID: $($response.requestId)" -ForegroundColor Cyan
    }
    catch {
        Write-Host "❌ Failed to send OpsGenie alert:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

# Test Slack Notification
function Test-SlackAlert {
    param (
        [string]$webhookUrl = $env:SLACK_WEBHOOK_URL,
        [string]$channel = "#alerts",
        [string]$message = "Test Alert from Trading System",
        [string]$color = "#36a64f"
    )
    
    if (-not $webhookUrl) {
        Write-Host "Slack webhook URL not found. Please set SLACK_WEBHOOK_URL environment variable." -ForegroundColor Yellow
        return
    }
    
    $payload = @{
        channel = $channel
        username = "Trading Bot"
        text = $message
        attachments = @(
            @{
                color = $color
                fields = @(
                    @{
                        title = "Status"
                        value = "This is a test notification"
                        short = $true
                    },
                    @{
                        title = "Environment"
                        value = "Development"
                        short = $true
                    }
                )
                footer = "Trading System"
                ts = [int][double]::Parse((Get-Date -UFormat %s))
            }
        )
    } | ConvertTo-Json -Depth 5
    
    try {
        $response = Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $payload -ContentType 'application/json'
        Write-Host "✅ Slack test notification sent successfully!" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to send Slack notification:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

# Test Microsoft Teams Notification
function Test-TeamsAlert {
    param (
        [string]$webhookUrl = $env:TEAMS_WEBHOOK_URL,
        [string]$title = "Test Alert from Trading System",
        [string]$message = "This is a test alert to verify Microsoft Teams integration.",
        [string]$themeColor = "0076D7"
    )
    
    if (-not $webhookUrl) {
        Write-Host "Microsoft Teams webhook URL not found. Please set TEAMS_WEBHOOK_URL environment variable." -ForegroundColor Yellow
        return
    }
    
    $body = @{
        "@type" = "MessageCard"
        "@context" = "http://schema.org/extensions"
        "themeColor" = $themeColor
        "summary" = $title
        "sections" = @(
            @{
                "activityTitle" = $title
                "activitySubtitle" = "Test Notification"
                "activityImage" = "https://img.icons8.com/color/96/000000/security-checked--v1.png"
                "facts" = @(
                    @{
                        "name" = "Status"
                        "value" = "Test Alert"
                    },
                    @{
                        "name" = "Environment"
                        "value" = "Development"
                    },
                    @{
                        "name" = "Time"
                        "value" = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
                    }
                )
                "markdown" = $true
            }
        )
    } | ConvertTo-Json -Depth 5
    
    try {
        $response = Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $body -ContentType 'application/json'
        Write-Host "✅ Microsoft Teams test notification sent successfully!" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to send Microsoft Teams notification:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

# Test SMS via Twilio
function Test-SmsAlert {
    param (
        [string]$accountSid = $env:TWILIO_ACCOUNT_SID,
        [string]$authToken = $env:TWILIO_AUTH_TOKEN,
        [string]$fromNumber = $env:TWILIO_FROM_NUMBER,
        [string]$toNumber = $env:TWILIO_TO_NUMBER,
        [string]$message = "Test SMS from Trading System"
    )
    
    if (-not $accountSid -or -not $authToken) {
        Write-Host "Twilio credentials not found. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables." -ForegroundColor Yellow
        return
    }
    
    if (-not $fromNumber) {
        Write-Host "Twilio from number not found. Please set TWILIO_FROM_NUMBER environment variable." -ForegroundColor Yellow
        return
    }
    
    if (-not $toNumber) {
        $toNumber = Read-Host "Enter the phone number to send the test SMS to (E.164 format, e.g., +1234567890)"
    }
    
    $uri = "https://api.twilio.com/2010-04-01/Accounts/$accountSid/Messages.json"
    $base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(($accountSid + ":" + $authToken)))
    
    $body = @{
        From = $fromNumber
        To = $toNumber
        Body = $message
    }
    
    try {
        $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType 'application/x-www-form-urlencoded' -Headers @{Authorization = "Basic $base64AuthInfo"}
        Write-Host "✅ Test SMS sent successfully to $toNumber" -ForegroundColor Green
        Write-Host "   Message SID: $($response.sid)" -ForegroundColor Cyan
    }
    catch {
        Write-Host "❌ Failed to send SMS:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

# Main menu
function Show-Menu {
    Clear-Host
    Write-Host "=== Trading System Alert Testing Tool ===" -ForegroundColor Cyan
    Write-Host "1. Test OpsGenie Alert"
    Write-Host "2. Test Slack Notification"
    Write-Host "3. Test Microsoft Teams Notification"
    Write-Host "4. Test SMS Alert (Twilio)"
    Write-Host "5. Test All Notifications"
    Write-Host "Q. Quit"
    Write-Host "`n"
}

# Main execution
$choice = $null
while ($choice -ne "Q") {
    Show-Menu
    $choice = Read-Host "Select an option (1-5 or Q to quit)"
    
    switch ($choice) {
        "1" { Test-OpsGenieAlert }
        "2" { Test-SlackAlert }
        "3" { Test-TeamsAlert }
        "4" { Test-SmsAlert }
        "5" { 
            Test-OpsGenieAlert
            Test-SlackAlert
            Test-TeamsAlert
            Test-SmsAlert
        }
        "Q" { Write-Host "Exiting..." -ForegroundColor Cyan }
        default { Write-Host "Invalid option. Please try again." -ForegroundColor Red }
    }
    
    if ($choice -ne "Q") {
        Write-Host "`nPress any key to continue..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}
