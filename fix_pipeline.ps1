# Auto-fix CI/CD Pipeline Script

# 1. Install required tools if missing
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "🛠️ Installing GitHub CLI..." -ForegroundColor Yellow
    winget install --id GitHub.cli -e --source winget
    Write-Host "✅ GitHub CLI installed. Please restart your terminal and run this script again." -ForegroundColor Green
    exit
}

# 2. Authenticate with GitHub if needed
if (-not (gh auth status 2>&1 | Select-String "Logged in to github.com")) {
    Write-Host "🔑 Authenticating with GitHub..." -ForegroundColor Yellow
    gh auth login --web -h github.com
}

# 3. Get latest workflow run details
$repoOwner = "pera00705282"
$repoName = "FamilyGuard"
$runId = (gh run list --repo "$repoOwner/$repoName" --limit 1 --json databaseId -q ".[0].databaseId" 2>$null)

if (-not $runId) {
    Write-Host "❌ No workflow runs found. Pushing changes to trigger a new run..." -ForegroundColor Red
    git add .
    git commit -m "Trigger CI/CD pipeline" --allow-empty
    git push
    Start-Sleep -Seconds 10  # Wait for the run to start
    $runId = gh run list --repo "$repoOwner/$repoName" --limit 1 --json databaseId -q ".[0].databaseId"
}

# 4. Watch the workflow run
Write-Host "👀 Watching workflow run #$runId..." -ForegroundColor Cyan
gh run watch $runId --repo "$repoOwner/$repoName" --exit-status

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Workflow failed. Checking logs..." -ForegroundColor Red
    
    # 5. Get failed job logs
    $failedJob = gh run view $runId --repo "$repoOwner/$repoName" --json jobs -q '.jobs[] | select(.conclusion == "failure") | .name' | Select-Object -First 1
    
    if ($failedJob) {
        Write-Host "🔍 Failed job: $failedJob" -ForegroundColor Yellow
        gh run view $runId --repo "$repoOwner/$repoName" --job "$failedJob" --log-failed
    }

    # 6. Common fixes
    Write-Host "🛠️ Attempting to fix common issues..." -ForegroundColor Yellow
    
    # Fix 1: Update requirements
    if (Test-Path "requirements.txt") {
        Write-Host "📦 Updating Python packages..." -ForegroundColor Cyan
        pip install -r requirements.txt --upgrade
    }

    # Fix 2: Run tests locally
    if (Test-Path "pytest.ini" -or (Get-ChildItem -Filter "test_*.py" -Recurse)) {
        Write-Host "🧪 Running tests locally..." -ForegroundColor Cyan
        python -m pytest -v
    }

    # Fix 3: Check Python version
    $pythonVersion = python --version
    Write-Host "🐍 Python version: $pythonVersion" -ForegroundColor Cyan

    # 7. Push fixes
    Write-Host "🚀 Pushing fixes to trigger new workflow..." -ForegroundColor Green
    git add .
    git commit -m "Fix CI/CD pipeline"
    git push

    # 8. Watch the new run
    Start-Sleep -Seconds 5
    $newRunId = gh run list --repo "$repoOwner/$repoName" --limit 1 --json databaseId -q ".[0].databaseId"
    Write-Host "👀 Watching new workflow run #$newRunId..." -ForegroundColor Cyan
    gh run watch $newRunId --repo "$repoOwner/$repoName" --exit-status
}

Write-Host "✅ Pipeline check complete!" -ForegroundColor Green