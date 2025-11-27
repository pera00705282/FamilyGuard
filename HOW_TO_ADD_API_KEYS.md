# How to Add API Keys - Simple Guide

## 🚀 Quick Method (Recommended)

Run the interactive setup script:

```bash
python setup_api_keys.py
```

This will:
- ✅ Guide you step-by-step
- ✅ Hide your input (secure)
- ✅ Set up sandbox mode automatically
- ✅ Save everything correctly

## 📝 Manual Method

### Step 1: Open the Config File

Edit: `config/config.yaml`

### Step 2: Find Your Exchange Section

For **Binance**, find:
```yaml
exchanges:
  binance:
    api_key: "YOUR_BINANCE_API_KEY"    # ← Replace this
    secret: "YOUR_BINANCE_SECRET"      # ← Replace this
    sandbox: true                       # ← Keep true for testing!
```

### Step 3: Replace the Placeholders

Replace `YOUR_BINANCE_API_KEY` with your actual API key (keep the quotes):
```yaml
api_key: "abc123xyz789youractualapikey"
secret: "def456uvw012youractualsecretkey"
```

### Step 4: Do the Same for Other Exchanges

**Coinbase** (needs passphrase too):
```yaml
coinbase:
  api_key: "your_coinbase_api_key"
  secret: "your_coinbase_secret"
  passphrase: "your_coinbase_passphrase"  # Required!
  sandbox: true
```

**Kraken**:
```yaml
kraken:
  api_key: "your_kraken_api_key"
  secret: "your_kraken_secret"
  sandbox: true
```

## 🔑 Where to Get API Keys

### Binance
1. Go to: https://www.binance.com/en/my/settings/api-management
2. Click "Create API"
3. Enable only: "Enable Reading" and "Enable Spot & Margin Trading"
4. ⚠️ **IMPORTANT:** Enable "Restrict access to trusted IPs only"
5. Copy API Key and Secret Key

**Testnet:** https://testnet.binance.vision/ (for sandbox testing)

### Coinbase
1. Go to: https://www.coinbase.com/settings/api
2. Click "Create API Key"
3. Copy: API Key, Secret Key, and **Passphrase** (all 3 needed!)

### Kraken
1. Go to: https://www.kraken.com/u/security/api
2. Click "Generate API Key"
3. Copy: API Key and Secret Key

## ✅ Verify Your Setup

After adding keys, test the configuration:

```bash
# Set PYTHONPATH
$env:PYTHONPATH="src"  # PowerShell

# Test loading config
python -c "from crypto_trading.utils.config import load_config; load_config('config/config.yaml'); print('✅ Config is valid!')"
```

## ⚠️ Security Checklist

- [ ] ✅ `sandbox: true` is set (for testing)
- [ ] ✅ `enable_live_trading: false` (keep false until tested)
- [ ] ✅ API keys have minimum permissions
- [ ] ✅ IP whitelisting enabled on exchange (if possible)
- [ ] ✅ `config/config.yaml` is in `.gitignore` (should be automatic)
- [ ] ✅ Never share your API keys

## 🎯 Example Config

Here's what a complete config looks like:

```yaml
exchanges:
  binance:
    api_key: "your_actual_binance_api_key_here"
    secret: "your_actual_binance_secret_here"
    sandbox: true
    rate_limit: 100
    enable_rate_limit: true

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

enable_live_trading: false  # ⚠️ Keep false!
log_level: "INFO"
```

## 🆘 Need Help?

- **Config file location:** `config/config.yaml`
- **Template location:** `config/config_template.yaml.java`
- **Full guide:** See `API_KEYS_SETUP.md` for detailed instructions

---

**Remember:** Always test in sandbox mode first! 🛡️

