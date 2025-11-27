# 🚀 Crypto Trading Bot - Setup Guide

## 📋 PREDUSLOVI

### Python Requirements
```bash
# Instaliraj Python 3.8+
python --version  # Treba biti 3.8 ili noviji

# Instaliraj pip
python -m pip install --upgrade pip
```

### TA-Lib Installation (OBAVEZNO!)
```bash
# Ubuntu/Debian
sudo apt-get install build-essential
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib

# Windows
# Preuzmi wheel sa: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
pip install TA_Lib-0.4.24-cp39-cp39-win_amd64.whl  # Prilagodi verziju

# macOS
brew install ta-lib
pip install TA-Lib
```

## 🛠️ INSTALACIJA

### 1. Ekstraktuj projekat
```bash
tar -xzf crypto_trading_project.tar.gz
cd project/
```

### 2. Kreiraj virtual environment
```bash
python -m venv crypto_trading_env
source crypto_trading_env/bin/activate  # Linux/Mac
# ili
crypto_trading_env\Scripts\activate     # Windows
```

### 3. Instaliraj dependencies
```bash
pip install -r requirements.txt
```

### 4. Kreiraj .env fajl za API ključeve
```bash
# Kreiraj config/.env fajl
touch config/.env
chmod 600 config/.env  # Samo ti možeš da čitaš

# Dodaj u config/.env:
BINANCE_API_KEY=your_real_binance_api_key
BINANCE_SECRET=your_real_binance_secret
COINBASE_API_KEY=your_coinbase_api_key
COINBASE_SECRET=your_coinbase_secret
COINBASE_PASSPHRASE=your_coinbase_passphrase
KRAKEN_API_KEY=your_kraken_api_key
KRAKEN_SECRET=your_kraken_secret
```

### 5. Ažuriraj config.yaml
```yaml
# U config/config.yaml promeni:
exchanges:
  binance:
    api_key: ${BINANCE_API_KEY}
    secret: ${BINANCE_SECRET}
    # ... ostalo
  coinbase:
    api_key: ${COINBASE_API_KEY}
    secret: ${COINBASE_SECRET}
    passphrase: ${COINBASE_PASSPHRASE}
    # ... ostalo
  kraken:
    api_key: ${KRAKEN_API_KEY}
    secret: ${KRAKEN_SECRET}
    # ... ostalo
```

## 🔧 KONFIGURACIJA

### 1. Testiraj instalaciju
```bash
python scripts/crypto_trading_cli.py --help
python scripts/crypto_trading_cli.py validate
```

### 2. Testiraj konekcije
```bash
python scripts/crypto_trading_cli.py test
```

### 3. Proveri status
```bash
python scripts/crypto_trading_cli.py status
```

## 🚀 POKRETANJE

### Demo Mode (PREPORUČENO ZA POČETAK)
```bash
python scripts/crypto_trading_cli.py demo
```

### Live Trading (OPREZ!)
```bash
# Počni sa malim amounts!
python scripts/crypto_trading_cli.py run
```

### Monitoring Dashboard
```bash
python scripts/crypto_trading_cli.py monitor
```

## 📊 KOMPONENTE SISTEMA

### ✅ TESTIRANE I FUNKCIONALNE:
- **ExchangeManager** - CCXT integracija sa 3 berze
- **Trading Strategije** - MA, RSI, MACD, Bollinger Bands
- **Risk Management** - Position sizing, stop loss, take profit
- **Portfolio Tracking** - Real-time PnL, pozicije, trade istorija
- **WebSocket Feeds** - Real-time market data
- **CLI Interface** - Kompletno funkcionalan

### 🛡️ SIGURNOSNE MERE:
- API ključevi u environment varijablama
- Rate limiting za API pozive
- HTTPS konekcije
- Error handling
- Input validacija

## ⚠️ VAŽNE NAPOMENE

### SIGURNOST:
1. **NIKAD ne deli API ključeve**
2. **Počni sa DEMO mode**
3. **Koristi MALE amounts za testiranje**
4. **Redovno pravi backup**

### PREPORUČENE POSTAVKE ZA POČETAK:
```yaml
risk_management:
  max_position_size_pct: 5.0    # Max 5% po trade
  stop_loss_pct: 1.0           # 1% stop loss
  take_profit_pct: 2.0         # 2% take profit
  max_daily_loss_pct: 10.0     # Max 10% dnevni gubitak
```

### MONITORING:
- Prati log fajlove u `logs/`
- Koristi `status` komandu redovno
- Postavi alerts za velike gubite

## 🆘 TROUBLESHOOTING

### Česti problemi:
1. **TA-Lib greška** - Instaliraj TA-Lib biblioteku
2. **API greške** - Proveri API ključeve i permissions
3. **Network greške** - Proveri internet konekciju
4. **Permission denied** - `chmod 600 config/.env`

### Log fajlovi:
```bash
tail -f logs/crypto_trading.log
tail -f logs/error.log
```

## 📞 PODRŠKA

Ako imaš probleme:
1. Proveri log fajlove
2. Pokreni `validate` komandu
3. Testiraj sa `demo` mode
4. Proveri API ključeve i permissions

---

**🎉 ALAT JE SPREMAN ZA REAL TRADING!**

**Počni sa demo mode, zatim sa malim amounts!** 🚀💰