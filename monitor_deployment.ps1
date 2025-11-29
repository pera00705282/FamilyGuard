# Monitor Deployment Script

# Check if GitHub CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GitHub CLI is not installed. Installing now..." -ForegroundColor Yellow
    winget install --id GitHub.cli
    Write-Host "Please restart your terminal after GitHub CLI installation and run this script again." -ForegroundColor Red
    exit
}

# Get repository info
$repoOwner = "pera00705282"
$repoName = "FamilyGuard"
$repoUrl = "https://github.com/$repoOwner/$repoName"

# Function to check workflow status
function Get-WorkflowStatus {
    Write-Host "`n🔄 Checking GitHub Actions status..." -ForegroundColor Cyan
    gh workflow list --repo $repoUrl
    $runs = gh run list --repo $repoUrl --limit 1 --json status,conclusion,event,headBranch,url | ConvertFrom-Json
    return $runs
}

# Function to update secrets
function Update-Secrets {
    Write-Host "`n🔑 Updating GitHub Secrets" -ForegroundColor Cyan
    Write-Host "Current secrets:" -ForegroundColor Yellow
    gh secret list --repo $repoUrl
    
    $secrets = @{
        "STAGING_SSH_PRIVATE_KEY" = "Your SSH private key"
        "STAGING_HOST" = "your-server-ip-or-domain"
        "STAGING_SSH_PORT" = "22"
        "STAGING_SSH_USER" = "ubuntu"
        "CODECOV_TOKEN" = "your-codecov-token"
        "SLACK_WEBHOOK_URL" = "your-slack-webhook"
    }
    
    foreach ($key in $secrets.Keys) {
        $update = Read-Host "Update $key? (y/n)"
        if ($update -eq 'y') {
            $value = Read-Host "Enter value for $key" -AsSecureString
            $value = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                [Runtime.InteropServices.Marshal]::SecureStringToBSTR($value)
            )
            $value | gh secret set $key --repo "$repoOwner/$repoName"
            Write-Host "✅ Updated $key" -ForegroundColor Green
        }
    }
}

# Function to check application status
function Get-ApplicationStatus {
    $stagingHost = gh secret get STAGING_HOST --repo $repoOwner/$repoName 2>$null
    if ($stagingHost) {
        Write-Host "`n🌐 Checking application status at: http://$stagingHost" -ForegroundColor Cyan
        try {
            $response = Invoke-WebRequest -Uri "http://$stagingHost" -UseBasicParsing -ErrorAction Stop
            Write-Host "✅ Application is running! Status code: $($response.StatusCode)" -ForegroundColor Green
        } catch {
            Write-Host "❌ Could not connect to the application. Error: $($_.Exception.Message)" -ForegroundColor Red
        }
    } else {
        Write-Host "⚠️  STAGING_HOST secret not set. Cannot check application status." -ForegroundColor Yellow
    }
}

# Main execution
Write-Host "`n🚀 Deployment Monitor for $repoUrl" -ForegroundColor Magenta
Write-Host "===================================" -ForegroundColor Magenta

# Check workflow status
$workflow = Get-WorkflowStatus
if ($workflow) {
    Write-Host "`nLatest workflow run:" -ForegroundColor Cyan
    $workflow | Format-Table -Property status, conclusion, event, headBranch, @{Name="URL";Expression={$_.url}}
    
    if ($workflow.status -eq "completed" -and $workflow.conclusion -eq "success") {
        Write-Host "✅ Last deployment was successful!" -ForegroundColor Green
        Get-ApplicationStatus
    } elseif ($workflow.status -eq "in_progress") {
        Write-Host "🔄 Workflow is still running. Monitoring progress..." -ForegroundColor Yellow
        gh run watch $workflow.id --repo $repoUrl --exit-status
        Get-ApplicationStatus
    } else {
        Write-Host "❌ Last deployment failed or was cancelled." -ForegroundColor Red
        Write-Host "Check the full logs at: $($workflow.url)" -ForegroundColor Yellow
    }
}

# Offer to update secrets
$updateSecrets = Read-Host "`nDo you want to update any secrets? (y/n)"
if ($updateSecrets -eq 'y') {
    Update-Secrets
}

# Open GitHub Actions in browser
$openBrowser = Read-Host "`nDo you want to open GitHub Actions in your browser? (y/n)"
if ($openBrowser -eq 'y') {
    Start-Process "https://github.com/$repoOwner/$repoName/actions"
}

Write-Host "`n✅ Monitoring complete!" -ForegroundColor Green