# 🚀 Crypto Trading Automation Tool

**Alat za potpunu automatizaciju konfiguracije za REAL TRADING sa pravim novcem!**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 📋 Pregled

Ovaj alat omogućava potpunu automatizaciju trgovanja kriptovalutama na vodećim berzama (Binance, Coinbase, Kraken) sa naprednim funkcionalnostima:

- ✅ **Unified API** preko CCXT biblioteke (100+ berzi)
- ✅ **Real-time WebSocket feeds** za live podatke
- ✅ **Napredne trading strategije** (MA, RSI, MACD, Bollinger Bands, Volume)
- ✅ **Kompletno risk management** (position sizing, stop loss, drawdown control)
- ✅ **Live monitoring i alerting** (Email, Telegram, Dashboard)
- ✅ **Production-ready kod** sa sigurnosnim proverama

## 🏗️ Struktura Projekta

```
crypto-trading-automation/
├── src/crypto_trading/           # Glavni source kod
│   ├── core/                     # Osnovne komponente
│   │   ├── main.py              # TradingBot, ExchangeManager
│   │   └── __init__.py
│   ├── strategies/               # Trading strategije
│   │   ├── manager.py           # Sve strategije i MultiStrategyManager
│   │   └── __init__.py
│   ├── portfolio/                # Portfolio management
│   │   ├── manager.py           # PortfolioManager, RiskManager
│   │   └── __init__.py
│   ├── monitoring/               # Monitoring i alerting
│   │   ├── monitor.py           # MetricsCollector, AlertManager
│   │   └── __init__.py
│   ├── utils/                    # Utility moduli
│   │   ├── config.py            # Konfiguracija
│   │   ├── logger.py            # Logging
│   │   ├── security.py          # Sigurnosne provere
│   │   └── __init__.py
│   └── __init__.py
├── config/                       # Konfiguracija
│   └── config_template.yaml     # Template konfiguracije
├── docs/                         # Dokumentacija
│   ├── README.md                # Detaljna dokumentacija
│   └── PROJECT_SUMMARY.md       # Pregled projekta
├── examples/                     # Primeri korišćenja
│   ├── demo.py                  # Kompletna demonstracija
│   ├── basic_usage.py           # Osnovni primeri
│   └── custom_strategy.py       # Custom strategije
├── scripts/                      # CLI scripts
│   └── crypto_trading_cli.py    # Glavni CLI interface
├── tests/                        # Unit testovi
│   ├── test_strategies.py       # Testovi strategija
│   └── __init__.py
├── requirements.txt              # Python dependencies
├── setup.py                     # Package setup
└── README.md                    # Ovaj fajl
```

## 🚀 Brza Instalacija

### 1. Preuzmi kod
```bash
git clone <repository-url>
cd crypto-trading-automation
```

### 2. Instaliraj dependencies
```bash
pip install -r requirements.txt
```

### 3. Kreiraj konfiguraciju
```bash
python scripts/crypto_trading_cli.py init
```

### 4. Konfiguriši API ključeve
Uredi `config/config.yaml` i dodaj svoje API ključeve:

```yaml
exchanges:
  binance:
    api_key: "YOUR_BINANCE_API_KEY"
    secret: "YOUR_BINANCE_SECRET"
    sandbox: true  # VAŽNO: Počni sa sandbox modom!
```

### 5. Validiraj sigurnost
```bash
python scripts/crypto_trading_cli.py validate
```

### 6. Testiraj konekcije
```bash
python scripts/crypto_trading_cli.py test
```

### 7. Pokreni demo
```bash
python examples/demo.py
```

### 8. Pokreni bot (DRY-RUN)
```bash
python scripts/crypto_trading_cli.py run --dry-run
```

## 🎯 Osnovne Komande

```bash
# CLI pomoć
python scripts/crypto_trading_cli.py --help

# Inicijalizacija
python scripts/crypto_trading_cli.py init

# Validacija konfiguracije
python scripts/crypto_trading_cli.py validate

# Test konekcija
python scripts/crypto_trading_cli.py test

# Pokretanje u dry-run modu
python scripts/crypto_trading_cli.py run --dry-run

# Pokretanje live trading-a (OPREZ!)
python scripts/crypto_trading_cli.py run

# Monitoring dashboard
python scripts/crypto_trading_cli.py monitor

# Status pregled
python scripts/crypto_trading_cli.py status

# Demo mode
python scripts/crypto_trading_cli.py demo
```

## 📈 Podržane Berze

| Berza | Spot Trading | Futures | WebSocket | Rate Limits |
|-------|-------------|---------|-----------|-------------|
| **Binance** | ✅ | ✅ | ✅ | 6,000/min |
| **Coinbase** | ✅ | ❌ | ✅ | 10/sec |
| **Kraken** | ✅ | ✅ | ✅ | 15-20/min |

## 🎯 Trading Strategije

### Implementirane Strategije
- **Moving Average Cross**: Fast/Slow MA crossover
- **RSI**: Relative Strength Index (oversold/overbought)
- **MACD**: Moving Average Convergence Divergence
- **Bollinger Bands**: Volatility-based signals
- **Volume Weighted**: Volume spike detection

### Predefinisane Kombinacije
- **Conservative**: MA(20,50) + RSI(14) + BB(20)
- **Aggressive**: MA(5,15) + RSI(7) + MACD + Volume
- **Scalping**: MA(3,8) + RSI(5) + Volume

### Custom Strategije
```python
from crypto_trading.strategies import BaseStrategy

class MyStrategy(BaseStrategy):
    async def analyze(self, symbol, data):
        # Tvoja logika ovde
        return Signal(...)
```

## 🛡️ Risk Management

- **Position Sizing**: Kelly Criterion + risk-based sizing
- **Stop Loss/Take Profit**: Automatski nivoi
- **Drawdown Control**: Maksimalni drawdown monitoring
- **Portfolio Risk**: Ukupan portfolio rizik
- **Daily Limits**: Maksimalan broj trade-ova
- **Correlation Risk**: Korelacijska analiza

## 📊 Monitoring i Alerting

### Metrike
- Portfolio balance i PnL
- Trading performance
- API latency i error rates
- System resources

### Alert Kanali
- **Email**: SMTP podrška
- **Telegram**: Bot integration
- **Webhook**: Custom endpoints
- **Console**: Real-time display

## 🔒 Sigurnost

### ⚠️ VAŽNA UPOZORENJA
- **POČNI SA SANDBOX MODOM!**
- **Testiraj strategije pre live trading-a**
- **Koristi manje iznose za početak**
- **Nikad ne investiraj više nego što možeš da izgubiš**

### Sigurnosne Provere
- API key format validacija
- Sandbox mode enforcement
- Risk parameter validacija
- Rate limiting compliance
- File permissions provere

## 📚 Primeri Korišćenja

### Osnovni Primer
```python
from crypto_trading import TradingBot

# Kreiranje bot-a
bot = TradingBot("config/config.yaml")
await bot.initialize()

# Pokretanje u dry-run modu
bot.dry_run = True
await bot.run()
```

### Custom Strategija
```python
from crypto_trading.strategies import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    async def analyze(self, symbol, data):
        # Analiza podataka
        if buy_condition:
            return Signal(
                symbol=symbol,
                action="buy",
                strength=0.8,
                price=current_price,
                strategy="MyStrategy"
            )
        return None
```

Više primera u `examples/` direktorijumu.

## 🧪 Testiranje

```bash
# Pokreni testove
python -m pytest tests/

# Test sa coverage
python -m pytest tests/ --cov=src/crypto_trading

# Test specifičnog modula
python -m pytest tests/test_strategies.py

# Automatizovani staging / sandbox run
python scripts/run_staging_plan.py --duration 900 --auto-config
```

## 📖 Dokumentacija

- **[Quick Start](QUICK_START.md)** – Zero-touch setup i bootstrap
- **[Staging / Sandbox Validation Plan](docs/STAGING_PLAN.md)** – Scenariji pre pravog novca
- **[Detaljna Dokumentacija](docs/README.md)** – Kompletno uputstvo
- **[Project Summary](docs/PROJECT_SUMMARY.md)** – Pregled projekta
- **[Examples](examples/)** – Primeri korišćenja

## 🤝 Doprinos

1. Fork repository
2. Kreiraj feature branch (`git checkout -b feature/nova-funkcionalnost`)
3. Commit promene (`git commit -am 'Dodaj novu funkcionalnost'`)
4. Push na branch (`git push origin feature/nova-funkcionalnost`)
5. Kreiraj Pull Request

## 📄 Licenca

Ovaj projekat je licenciran pod MIT licencom - pogledaj [LICENSE](LICENSE) fajl za detalje.

## ⚠️ Disclaimer

**UPOZORENJE**: Trading kriptovalutama nosi visok rizik gubitka kapitala. Ovaj alat je kreiran u edukacijske svrhe. Autor nije odgovoran za finansijske gubitke. Uvek testiraj u sandbox modu pre korišćenja sa pravim novcem.

## 📞 Podrška

- 📧 Email: openhands@all-hands.dev
- 📖 Dokumentacija: [docs/README.md](docs/README.md)
- 🐛 Issues: GitHub Issues
- 💬 Diskusije: GitHub Discussions

---

**🚀 Srećno trgovanje! 📈**

*Kreiran sa ❤️ od strane OpenHands AI Assistant*