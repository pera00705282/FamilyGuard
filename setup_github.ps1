# GitHub Repository Setup Script

# Check if GitHub CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GitHub CLI is not installed. Installing now..."
    winget install --id GitHub.cli
}

# Authenticate with GitHub if not already authenticated
if (-not (gh auth status 2>&1 | Select-String "Logged in to github.com")) {
    gh auth login
}

# Get repository name
$repoName = Split-Path (Get-Location) -Leaf
$repoOwner = (gh api user | ConvertFrom-Json).login

# Create GitHub secrets
$secrets = @{
    "STAGING_SSH_PRIVATE_KEY" = "YOUR_SSH_PRIVATE_KEY"  # Replace with your actual key
    "STAGING_HOST" = "your-server-ip-or-domain"         # Replace with your server
    "CODECOV_TOKEN" = $null  # Optional: Add your Codecov token if needed
    "STAGING_SSH_PORT" = "22"
    "STAGING_SSH_USER" = "ubuntu"
    "SLACK_WEBHOOK_URL" = $null  # Optional: Add your Slack webhook if needed
}

# Set GitHub secrets
foreach ($key in $secrets.Keys) {
    if ($secrets[$key]) {
        Write-Host "Setting secret: $key"
        $secretValue = $secrets[$key]
        $secretValue | gh secret set $key --repo "$repoOwner/$repoName"
    }
}

# Create GitHub environments
$environments = @("staging", "notifications")

foreach ($env in $environments) {
    Write-Host "Creating environment: $env"
    gh api -X PUT "repos/$repoOwner/$repoName/environments/$env" --silent
}

Write-Host "`n✅ GitHub repository setup complete!"
Write-Host "Next steps:"
Write-Host "1. Commit and push your changes"
Write-Host "2. Monitor the workflow in the Actions tab"