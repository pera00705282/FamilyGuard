# Quick Start Guide

## How to Start the Crypto Trading Tool

### Zero-Touch Setup (recommended)
The entire tool can now be installed and launched with a single command:

```bash
python scripts/bootstrap_tool.py --run-demo --run-dashboard
```

What this does:
1. Creates/re-uses `.venv`
2. Upgrades pip and installs everything from `requirements.txt`
3. Migrates any lingering API keys from `api/API_final.txt`
4. Runs the full pytest suite (omit with `--skip-tests`)
5. Pokreće `start_demo.py` (`--run-demo`)
6. Pokreće FastAPI Dashboard (`--run-dashboard`)

After it completes, activate the venv manually if you want to issue further commands:
- PowerShell: `.\\.venv\\Scripts\\Activate.ps1`
- Linux/Mac: `source .venv/bin/activate`

### Full Deploy (instalacija + start bota + Dashboard + ponovno šifrovanje)
```bash
python scripts/deploy_tool.py --mode bot --with-dashboard --encrypt-at-rest --delete-plain
```
Ovaj skript:
1. Pokreće bootstrap (kreira `.venv`, instalira dependency, migrira tajne)
2. Auto-konfiguriše `config/config.yaml` koristeći bezbedni store ili env
3. (Opcionalno) preskače testove (`--skip-tests`)
4. Pokreće Dashboard i/ili pravi trading bot (`crypto_trading.core.main run`)
5. Po završetku ponovo šifruje konfiguraciju i briše plaintext (ako je zadato)

---

### Prerequisites (manual flow)
1. Python 3.13 installed
2. All dependencies installed: `pip install -r requirements.txt`

### Step 1: Set Up Environment
```bash
# Set PYTHONPATH (required for imports)
# Windows PowerShell:
$env:PYTHONPATH="src"

# Windows CMD:
set PYTHONPATH=src

# Linux/Mac:
export PYTHONPATH=src
```

### Step 2: Initialize Configuration
```bash
# Create default configuration file
python -c "from src.crypto_trading.utils.config import create_default_config, save_config; config = create_default_config(); save_config(config, 'config/config.yaml')"
```

Or manually create `config/config.yaml`:
```yaml
exchanges:
  binance:
    api_key: "YOUR_BINANCE_API_KEY"
    secret: "YOUR_BINANCE_SECRET"
    sandbox: true
  coinbase:
    api_key: "YOUR_COINBASE_API_KEY"
    secret: "YOUR_COINBASE_SECRET"
    passphrase: "YOUR_COINBASE_PASSPHRASE"
    sandbox: true
  kraken:
    api_key: "YOUR_KRAKEN_API_KEY"
    secret: "YOUR_KRAKEN_SECRET"
    sandbox: true

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

enable_live_trading: false
log_level: "INFO"
```

### Step 3: Run Demo (Safest Way to Start)
```bash
# Set PYTHONPATH first
$env:PYTHONPATH="src"  # PowerShell
# OR
export PYTHONPATH=src  # Linux/Mac

# Run the demo
python examples/demo.py
```

### Step 4: Run Basic Example
```bash
# Set PYTHONPATH
$env:PYTHONPATH="src"

# Run basic usage example
python examples/basic_usage.py
```

### Step 5: Run Custom Strategy Example
```bash
# Set PYTHONPATH
$env:PYTHONPATH="src"

# Run custom strategy example
python examples/custom_strategy.py
```

## Running the Main Trading Bot

### Option 1: Using Python Directly
```python
# Create a script: run_bot.py
import asyncio
import sys
sys.path.insert(0, 'src')

from crypto_trading.core.main import TradingBot
from crypto_trading.utils.config import load_config

async def main():
    # Load configuration
    config = load_config('config/config.yaml')
    
    # Create bot instance
    bot = TradingBot(config)
    
    # Start bot (will run in dry-run mode if enable_live_trading is False)
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
```

Then run:
```bash
$env:PYTHONPATH="src"
python run_bot.py
```

### Option 2: Using the Demo Script
The demo script is the easiest way to see the tool in action:
```bash
$env:PYTHONPATH="src"
python examples/demo.py
```

## Important Notes

### ⚠️ Safety First
- **ALWAYS start with `sandbox: true`** in your config
- **NEVER enable `enable_live_trading: true`** until you've thoroughly tested
- The tool defaults to dry-run mode for safety

### Environment Variables
You can also set PYTHONPATH permanently:
- **Windows**: Add to System Environment Variables
- **Linux/Mac**: Add to `~/.bashrc` or `~/.zshrc`:
  ```bash
  export PYTHONPATH=/path/to/FamilyGuard/src
  ```

### Troubleshooting

**Import Errors?**
- Make sure `PYTHONPATH=src` is set
- Verify you're in the project root directory
- Check that all dependencies are installed: `pip install -r requirements.txt`

**Configuration Errors?**
- Ensure `config/config.yaml` exists
- Validate YAML syntax
- Check that at least one exchange is configured

**Module Not Found?**
- Run: `pip install -r requirements.txt`
- Verify Python version: `python --version` (should be 3.13+)

## Quick Test
```bash
# Test that everything works
$env:PYTHONPATH="src"
python -c "from crypto_trading.strategies import MovingAverageCrossStrategy; print('✅ Imports working!')"
```

## Easiest Way to Start (New!)

Just run one of these startup scripts:

**Windows PowerShell:**
```powershell
.\start_demo.ps1
```

**Windows/Linux/Mac (Python):**
```bash
python start_demo.py
```

**Linux/Mac (Bash):**
```bash
chmod +x start_demo.sh
./start_demo.sh
```

These scripts automatically set up the environment and run the demo!

## Next Steps
1. ✅ Run the demo to see it in action
2. ✅ Configure your API keys (sandbox mode first!)
3. ✅ Test with small amounts
4. ✅ Review the examples for customization
5. ✅ Read the full README.md for advanced features

