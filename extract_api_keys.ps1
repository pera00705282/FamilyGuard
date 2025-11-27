# Script za izvlačenje API ključeva iz zaštićenog foldera
# i formatiranje za FamilyGuard tool

param(
    [string]$SourceFolder = "C:\Users\Milan Jeremic\Desktop\API menjacnice",
    [string]$OutputFile = "config\config.yaml"
)

Write-Host "🔐 Izvlačenje API ključeva..." -ForegroundColor Cyan
Write-Host "=" * 60

# Učitaj encryption utilities
$sourceScript = Join-Path $SourceFolder "encryption-utils.ps1"
if (-not (Test-Path $sourceScript)) {
    Write-Host "❌ encryption-utils.ps1 nije pronađen!" -ForegroundColor Red
    exit 1
}

. $sourceScript

# Inicijalizuj encryption context
$context = Initialize-EncryptionContext -Folder $SourceFolder
Write-Host "✅ Encryption context inicijalizovan" -ForegroundColor Green

# Mapa exchange imena (zaštićeno -> FamilyGuard format)
$exchangeMap = @{
    "Binance" = "binance"
    "Coinbase" = "coinbase"
    "Kraken" = "kraken"
}

# Funkcija za dekriptovanje i parsiranje API ključeva
function Extract-APIKeys {
    param([string]$ExchangeName, [string]$SecureFolder, $Context)
    
    $protectedFile = Join-Path $SecureFolder "$ExchangeName.protected"
    
    if (-not (Test-Path $protectedFile)) {
        Write-Host "⚠️  $ExchangeName.protected nije pronađen" -ForegroundColor Yellow
        return $null
    }
    
    try {
        Write-Host "  📂 Dekriptujem $ExchangeName..." -ForegroundColor Yellow
        $encrypted = Get-Content -LiteralPath $protectedFile -Raw -ErrorAction Stop
        $plainText = Unprotect-Secret -CipherText $encrypted -KeyBytes $context.KeyBytes -IVBytes $context.IVBytes
        
        if ([string]::IsNullOrWhiteSpace($plainText)) {
            Write-Host "  ⚠️  $ExchangeName je prazan" -ForegroundColor Yellow
            return $null
        }
        
        # Parsiraj plain text (može biti JSON, YAML, ili plain text)
        $keys = @{}
        
        # Format: "API key name: <key>" i "Private key: <secret>"
        if ($plainText -match '(?i)API\s+key\s+name\s*:\s*(.+)') {
            $keys.api_key = $matches[1].Trim()
        }
        if ($plainText -match '(?i)Private\s+key\s*:\s*(.+)') {
            $keys.secret = $matches[1].Trim()
        }
        if ($plainText -match '(?i)Passphrase\s*:\s*(.+)') {
            $keys.passphrase = $matches[1].Trim()
        }
        
        # Pokušaj JSON format ako nismo našli
        if (-not $keys.api_key) {
            try {
                $json = $plainText | ConvertFrom-Json
                if ($json.api_key) { $keys.api_key = $json.api_key }
                if ($json.secret) { $keys.secret = $json.secret }
                if ($json.secret_key) { $keys.secret = $json.secret_key }
                if ($json.passphrase) { $keys.passphrase = $json.passphrase }
                if ($json.apiKey) { $keys.api_key = $json.apiKey }
                if ($json.apiSecret) { $keys.secret = $json.apiSecret }
            }
            catch {
                # Pokušaj YAML format
                try {
                    if ($plainText -match '(?i)api[_-]?key["\s:]+([^\s"\n]+)') {
                        $keys.api_key = $matches[1].Trim('"', "'", ' ')
                    }
                    if ($plainText -match '(?i)secret["\s:]+([^\s"\n]+)') {
                        $keys.secret = $matches[1].Trim('"', "'", ' ')
                    }
                    if ($plainText -match '(?i)passphrase["\s:]+([^\s"\n]+)') {
                        $keys.passphrase = $matches[1].Trim('"', "'", ' ')
                    }
                }
                catch {
                    # Plain text format - pokušaj da izvučemo linije
                    $lines = $plainText -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
                    foreach ($line in $lines) {
                        if ($line -match '(?i)api[_-]?key["\s:=]+([^\s"\n]+)') {
                            $keys.api_key = $matches[1].Trim('"', "'", ' ', '=')
                        }
                        if ($line -match '(?i)secret["\s:=]+([^\s"\n]+)') {
                            $keys.secret = $matches[1].Trim('"', "'", ' ', '=')
                        }
                        if ($line -match '(?i)passphrase["\s:=]+([^\s"\n]+)') {
                            $keys.passphrase = $matches[1].Trim('"', "'", ' ', '=')
                        }
                    }
                }
            }
        }
        
        # Ako nismo našli ništa, možda je plain text sa novim redovima
        if ($keys.Count -eq 0) {
            $lines = $plainText -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
            if ($lines.Count -ge 1) { $keys.api_key = $lines[0].Trim() }
            if ($lines.Count -ge 2) { $keys.secret = $lines[1].Trim() }
            if ($lines.Count -ge 3) { $keys.passphrase = $lines[2].Trim() }
        }
        
        if ($keys.api_key -and $keys.secret) {
            Write-Host "  ✅ $ExchangeName uspešno izvučen" -ForegroundColor Green
            return $keys
        }
        else {
            Write-Host "  ⚠️  $ExchangeName - nedostaju ključevi (api_key ili secret)" -ForegroundColor Yellow
            Write-Host "  📄 Raw content (prvih 100 karaktera): $($plainText.Substring(0, [Math]::Min(100, $plainText.Length)))" -ForegroundColor Gray
            return $null
        }
    }
    catch {
        Write-Host "  ❌ Greška pri dekriptovanju $ExchangeName : $_" -ForegroundColor Red
        return $null
    }
}

# Izvuci ključeve za sve podržane exchange-ove
$secureFolder = Join-Path $SourceFolder "secure"
$extractedKeys = @{}

foreach ($protectedName in $exchangeMap.Keys) {
    $keys = Extract-APIKeys -ExchangeName $protectedName -SecureFolder $secureFolder -Context $context
    if ($keys) {
        $extractedKeys[$exchangeMap[$protectedName]] = $keys
    }
}

Write-Host "`n📊 Rezultati:" -ForegroundColor Cyan
Write-Host "=" * 60
foreach ($exchange in $extractedKeys.Keys) {
    Write-Host "  ✅ $exchange : API Key pronađen" -ForegroundColor Green
}

if ($extractedKeys.Count -eq 0) {
    Write-Host "❌ Nisu pronađeni API ključevi!" -ForegroundColor Red
    exit 1
}

# Učitaj postojeću konfiguraciju ili kreiraj novu
$configPath = Join-Path (Get-Location) $OutputFile
$configDir = Split-Path $configPath -Parent

if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}

# Učitaj postojeću konfiguraciju ako postoji
$existingConfig = $null
if (Test-Path $configPath) {
    try {
        $existingConfig = Get-Content $configPath -Raw | ConvertFrom-Yaml
        Write-Host "✅ Postojeća konfiguracija učitana" -ForegroundColor Green
    }
    catch {
        Write-Host "⚠️  Ne mogu da učitam postojeću konfiguraciju, kreiram novu" -ForegroundColor Yellow
    }
}

# Ažuriraj ili kreiraj konfiguraciju
if (-not $existingConfig) {
    $existingConfig = @{
        exchanges = @{}
        trading = @{
            symbols = @("BTC/USDT", "ETH/USDT")
            strategies = @("conservative")
            max_positions = 5
            risk_management = @{
                max_position_size = 0.1
                stop_loss_pct = 0.02
                take_profit_pct = 0.04
                max_daily_trades = 20
                max_drawdown_pct = 0.15
            }
        }
        monitoring = @{
            enable_alerts = $true
            alert_channels = @("console")
            metrics_retention_hours = 168
            email = @{
                smtp_server = "smtp.gmail.com"
                smtp_port = 587
                username = ""
                password = ""
                to_addresses = @()
            }
            telegram = @{
                bot_token = ""
                chat_ids = @()
            }
        }
        enable_live_trading = $false
        log_level = "INFO"
    }
}

# Ažuriraj exchange konfiguracije
if (-not $existingConfig.exchanges) {
    $existingConfig.exchanges = @{}
}

foreach ($exchangeName in $extractedKeys.Keys) {
    $keys = $extractedKeys[$exchangeName]
    
    $exchangeConfig = @{
        api_key = $keys.api_key
        secret = $keys.secret
        sandbox = $true  # Uvek sandbox za sigurnost
        rate_limit = 100
        enable_rate_limit = $true
    }
    
    if ($keys.passphrase) {
        $exchangeConfig.passphrase = $keys.passphrase
    }
    else {
        $exchangeConfig.passphrase = $null
    }
    
    $existingConfig.exchanges[$exchangeName] = $exchangeConfig
    Write-Host "✅ $exchangeName ažuriran u konfiguraciji" -ForegroundColor Green
}

# Konvertuj u YAML i sačuvaj
try {
    # Koristimo jednostavan YAML format
    $yamlContent = @"
# Crypto Trading Tool Configuration
# Auto-generated from encrypted API keys
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

exchanges:
"@

    foreach ($exchangeName in ($existingConfig.exchanges.Keys | Sort-Object)) {
        $ex = $existingConfig.exchanges[$exchangeName]
        $yamlContent += "`n  $exchangeName`:"
        $yamlContent += "`n    api_key: `"$($ex.api_key)`""
        $yamlContent += "`n    secret: `"$($ex.secret)`""
        if ($ex.passphrase) {
            $yamlContent += "`n    passphrase: `"$($ex.passphrase)`""
        }
        else {
            $yamlContent += "`n    passphrase: null"
        }
        $yamlContent += "`n    sandbox: $($ex.sandbox.ToString().ToLower())"
        $yamlContent += "`n    rate_limit: $($ex.rate_limit)"
        $yamlContent += "`n    enable_rate_limit: $($ex.enable_rate_limit.ToString().ToLower())"
    }

    $yamlContent += @"

trading:
  symbols:
    - "BTC/USDT"
    - "ETH/USDT"
  strategies:
    - "conservative"
  max_positions: 5
  risk_management:
    max_position_size: 0.1
    stop_loss_pct: 0.02
    take_profit_pct: 0.04
    max_daily_trades: 20
    max_drawdown_pct: 0.15

monitoring:
  enable_alerts: true
  alert_channels:
    - "console"
  metrics_retention_hours: 168
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: ""
    password: ""
    to_addresses: []
  telegram:
    bot_token: ""
    chat_ids: []

enable_live_trading: false
log_level: "INFO"
"@

    Set-Content -Path $configPath -Value $yamlContent -Encoding UTF8
    Write-Host "`n✅ Konfiguracija sačuvana u: $configPath" -ForegroundColor Green
    Write-Host "`n⚠️  VAŽNO:" -ForegroundColor Yellow
    Write-Host "   - Sandbox mode je automatski omogućen (sandbox: true)" -ForegroundColor Yellow
    Write-Host "   - Live trading je onemogućen (enable_live_trading: false)" -ForegroundColor Yellow
    Write-Host "   - Proveri konfiguraciju pre korišćenja!" -ForegroundColor Yellow
}
catch {
    Write-Host "❌ Greška pri čuvanju konfiguracije: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 Gotovo! API ključevi su izvučeni i konfiguracija je ažurirana." -ForegroundColor Green

