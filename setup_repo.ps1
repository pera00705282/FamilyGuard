# Setup Repository and CI/CD Automation Script

# Function to check if a command exists
function Test-CommandExists {
    param($command)
    $exists = $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
    return $exists
}

# Check if Git is installed
if (-not (Test-CommandExists "git")) {
    Write-Host "Git is not installed. Installing Git..." -ForegroundColor Yellow
    winget install --id Git.Git -e --source winget
    Write-Host "Please restart your terminal after Git installation and run this script again." -ForegroundColor Red
    exit
}

# Check if GitHub CLI is installed
if (-not (Test-CommandExists "gh")) {
    Write-Host "GitHub CLI is not installed. Installing GitHub CLI..." -ForegroundColor Yellow
    winget install --id GitHub.cli
    Write-Host "GitHub CLI installed. Please authenticate when prompted." -ForegroundColor Green
}

# Authenticate with GitHub if not already authenticated
if (-not (gh auth status 2>&1 | Select-String "Logged in to github.com")) {
    Write-Host "Authenticating with GitHub..." -ForegroundColor Yellow
    gh auth login --web -h github.com
}

# Create a new GitHub repository
$repoName = Split-Path (Get-Location) -Leaf
$repoOwner = (gh api user | ConvertFrom-Json).login

Write-Host "`nCreating GitHub repository: $repoName" -ForegroundColor Cyan
$repoUrl = gh repo create $repoName --public --source=. --remote=origin --push 2>&1

if ($LASTEXITCODE -ne 0) {
    if ($repoUrl -like "*already exists*") {
        Write-Host "Repository already exists. Connecting to existing repository..." -ForegroundColor Yellow
        git remote add origin "https://github.com/$repoOwner/$repoName.git"
    } else {
        Write-Host "Failed to create repository: $repoUrl" -ForegroundColor Red
        exit 1
    }
}

# Set up the main branch
Write-Host "`nSetting up main branch..." -ForegroundColor Cyan
git branch -M main

# Add all files and make initial commit
Write-Host "`nAdding files and creating initial commit..." -ForegroundColor Cyan
git add .
git commit -m "Initial commit: Set up CI/CD pipeline and project structure"

# Push to GitHub
Write-Host "`nPushing to GitHub..." -ForegroundColor Cyan
git push -u origin main

# Create GitHub secrets (will only work if you have admin access)
$secrets = @{
    "STAGING_SSH_PRIVATE_KEY" = "YOUR_SSH_PRIVATE_KEY"  # Replace with your actual key
    "STAGING_HOST" = "your-server-ip-or-domain"         # Replace with your server
    "STAGING_SSH_PORT" = "22"
    "STAGING_SSH_USER" = "ubuntu"
}

Write-Host "`nSetting up GitHub secrets..." -ForegroundColor Cyan
foreach ($key in $secrets.Keys) {
    if ($secrets[$key]) {
        Write-Host "Setting secret: $key" -ForegroundColor Yellow
        $secretValue = $secrets[$key]
        $secretValue | gh secret set $key --repo "$repoOwner/$repoName"
    }
}

# Create GitHub environments
$environments = @("staging", "notifications")

Write-Host "`nSetting up GitHub environments..." -ForegroundColor Cyan
foreach ($env in $environments) {
    Write-Host "Creating environment: $env" -ForegroundColor Yellow
    gh api -X PUT "repos/$repoOwner/$repoName/environments/$env" --silent
}

# Verify setup
Write-Host "`nVerifying setup..." -ForegroundColor Cyan
Write-Host "Repository URL: https://github.com/$repoOwner/$repoName" -ForegroundColor Green
Write-Host "GitHub Actions should now be running. Check the Actions tab in your repository." -ForegroundColor Green

Write-Host "`n✅ Setup complete! Your repository is ready to use with CI/CD." -ForegroundColor Green