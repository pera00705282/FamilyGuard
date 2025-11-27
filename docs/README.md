# 🚀 Crypto Trading Automation Tool

**Alat za potpunu automatizaciju konfiguracije za REAL TRADING sa pravim novcem!**

⚠️ **UPOZORENJE**: Ovaj alat je dizajniran za trgovanje sa pravim novcem. Koristite ga na vlastitu odgovornost!

## 🌟 Funkcionalnosti

### 📊 Podržane Berze
- **Binance** (Spot & Futures)
- **Coinbase Advanced Trade**
- **Kraken** (Spot & Futures)

### 🎯 Trading Strategije
- Moving Average Crossover
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Volume Weighted Strategy
- Multi-Strategy kombinacije

### 🛡️ Risk Management
- Automatski stop loss i take profit
- Position sizing na osnovu rizika
- Portfolio diversifikacija
- Drawdown kontrola
- Korelacijski risk management

### 📈 Real-time Monitoring
- Live WebSocket feeds
- Portfolio tracking
- Performance metrike
- System health monitoring
- Alerting sistem

### 🔔 Alerting i Notifikacije
- Email notifikacije
- Telegram bot
- Webhook integracije
- Customizable alert rules

## 🚀 Brza Instalacija

### 1. Kloniraj ili preuzmi kod
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
python crypto_trading_automation.py init
```

### 4. Uredi konfiguraciju
Otvori `config.yaml` i dodaj svoje API ključeve:

```yaml
exchanges:
  binance:
    api_key: "YOUR_BINANCE_API_KEY"
    secret: "YOUR_BINANCE_SECRET"
    sandbox: true  # VAŽNO: Stavi false za live trading
```

### 5. Testiraj konekcije
```bash
python crypto_trading_automation.py test
```

### 6. Pokreni monitoring
```bash
python crypto_trading_automation.py monitor -s BTC/USDT
```

### 7. Pokreni bot (DEMO mode)
```bash
python crypto_trading_automation.py run
```

## ⚙️ Detaljno Podešavanje

### API Ključevi

#### Binance
1. Idi na [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Kreiraj novi API ključ
3. Omogući "Enable Trading" i "Enable Futures" (ako potrebno)
4. Dodaj IP adresu u whitelist
5. Kopiraj API Key i Secret

#### Coinbase
1. Idi na [Coinbase Advanced Trade API](https://www.coinbase.com/settings/api)
2. Kreiraj novi API ključ
3. Omogući potrebne permisije (View, Trade)
4. Kopiraj API Key, Secret i Passphrase

#### Kraken
1. Idi na [Kraken API Settings](https://www.kraken.com/u/security/api)
2. Kreiraj novi API ključ
3. Omogući potrebne permisije (Query Funds, Query Open Orders, Create & Modify Orders)
4. Kopiraj API Key i Private Key

### Konfiguracija Trading Strategije

```yaml
strategy:
  type: "multi_strategy"
  strategies:
    - name: "moving_average"
      weight: 0.3
      params:
        fast_period: 10
        slow_period: 30
    - name: "rsi"
      weight: 0.25
      params:
        period: 14
        oversold: 30
        overbought: 70
```

### Risk Management Podešavanje

```yaml
risk_management:
  max_position_size: 0.1        # 10% portfolia po poziciji
  stop_loss_pct: 0.02           # 2% stop loss
  take_profit_pct: 0.05         # 5% take profit
  risk_per_trade: 0.01          # 1% rizik po trade-u
  max_daily_trades: 10          # Maksimalno 10 trade-ova dnevno
```

## 🔧 Komande

### Osnovne Komande
```bash
# Kreiranje konfiguracije
python crypto_trading_automation.py init

# Testiranje konekcija
python crypto_trading_automation.py test

# Pokretanje bot-a
python crypto_trading_automation.py run

# Monitoring cena
python crypto_trading_automation.py monitor -s BTC/USDT
```

### Napredne Komande
```bash
# Pokretanje sa custom config
python crypto_trading_automation.py run -c my_config.yaml

# Monitoring više simbola
python crypto_trading_automation.py monitor -s BTC/USDT,ETH/USDT

# Debug mode
python crypto_trading_automation.py run --debug
```

## 📊 Monitoring i Dashboard

### Live Console Monitor
```bash
python crypto_trading_automation.py run
```
Prikazuje real-time podatke u terminalu.

### Web Dashboard
Kada je bot pokrenut, dashboard je dostupan na:
```
http://localhost:8080
```

### Metrike
- Portfolio balance i PnL
- Open pozicije
- Trading performance
- API latency i errors
- System resources

## 🔔 Alerting Setup

### Email Notifikacije
```yaml
alerts:
  enable_email: true
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: "your_email@gmail.com"
    password: "your_app_password"
    to_emails:
      - "alerts@example.com"
```

### Telegram Bot
1. Kreiraj bot kod @BotFather
2. Dobij bot token
3. Dobij chat ID
4. Konfiguriši:

```yaml
alerts:
  enable_telegram: true
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_ids:
      - "YOUR_CHAT_ID"
```

## 🛡️ Sigurnost

### Najbolje Prakse
1. **Nikad ne deli API ključeve**
2. **Koristi IP whitelist na berzama**
3. **Počni sa sandbox/demo modovima**
4. **Postavi razumne stop loss nivoe**
5. **Redovno proveravaj pozicije**
6. **Čuvaj backup konfiguracije**

### API Permisije
- **Binance**: Enable Trading, Enable Futures (opciono)
- **Coinbase**: View, Trade
- **Kraken**: Query Funds, Query Open Orders, Create & Modify Orders

### Rate Limiting
Alat automatski poštuje rate limits:
- **Binance**: 1200 requests/minute
- **Coinbase**: 10 requests/second
- **Kraken**: 15 calls/minute

## 📈 Trading Strategije

### Konzervativna Strategija
```python
def create_conservative_strategy():
    strategies = [
        MovingAverageCrossStrategy(fast_period=20, slow_period=50),
        RSIStrategy(period=14, oversold=25, overbought=75),
        BollingerBandsStrategy(period=20, std_dev=2.0)
    ]
    return MultiStrategyManager(strategies)
```

### Agresivna Strategija
```python
def create_aggressive_strategy():
    strategies = [
        MovingAverageCrossStrategy(fast_period=5, slow_period=15),
        RSIStrategy(period=7, oversold=35, overbought=65),
        MACDStrategy(fast_period=8, slow_period=21, signal_period=5),
        VolumeWeightedStrategy(period=10, volume_threshold=2.0)
    ]
    return MultiStrategyManager(strategies)
```

### Scalping Strategija
```python
def create_scalping_strategy():
    strategies = [
        MovingAverageCrossStrategy(fast_period=3, slow_period=8),
        RSIStrategy(period=5, oversold=40, overbought=60),
        VolumeWeightedStrategy(period=5, volume_threshold=3.0)
    ]
    return MultiStrategyManager(strategies)
```

## 🔍 Troubleshooting

### Česti Problemi

#### 1. API Ključevi ne rade
```
❌ Greška pri inicijalizaciji binance: Invalid API-key, IP, or permissions
```
**Rešenje**:
- Proveri da li su API ključevi ispravni
- Dodaj IP adresu u whitelist
- Proveri permisije na API ključu

#### 2. Rate Limit Exceeded
```
❌ Rate limit exceeded
```
**Rešenje**:
- Smanji `rate_limit` u konfiguraciji
- Povećaj `enable_rate_limit: true`

#### 3. Insufficient Balance
```
❌ Insufficient balance for trade
```
**Rešenje**:
- Proveri balance na berzi
- Smanji `max_position_size`
- Povećaj početni balance

#### 4. WebSocket Connection Failed
```
❌ WebSocket connection failed
```
**Rešenje**:
- Proveri internet konekciju
- Restartuj aplikaciju
- Proveri firewall settings

### Debug Mode
```bash
python crypto_trading_automation.py run --debug
```

### Log Fajlovi
- `crypto_trading.log` - Glavni log
- `portfolio_state.json` - Portfolio state
- `dashboard.html` - Web dashboard

## 📚 Dodatni Resursi

### Dokumentacija API-ja
- [Binance API Docs](https://developers.binance.com/)
- [Coinbase Advanced Trade API](https://docs.cdp.coinbase.com/advanced-trade/)
- [Kraken API Docs](https://docs.kraken.com/rest/)

### Trading Edukacija
- [Investopedia Trading](https://www.investopedia.com/trading-4427765)
- [TradingView Education](https://www.tradingview.com/education/)
- [Binance Academy](https://academy.binance.com/)

### Python Biblioteke
- [CCXT Documentation](https://docs.ccxt.com/)
- [Cryptofeed Documentation](https://github.com/bmoscon/cryptofeed)
- [TA-Lib Documentation](https://ta-lib.org/)

## ⚠️ Disclaimer

**VAŽNO**: Ovaj alat je kreiran u edukacijske svrhe. Trading kriptovalutama nosi visok rizik i može rezultovati gubitkom novca. 

- Autor nije odgovoran za finansijske gubitke
- Testiraj strategije u demo modu pre live trading-a
- Nikad ne investiraj više nego što možeš da izgubiš
- Konsultuj se sa finansijskim savetnicima

## 📄 Licenca

MIT License - Pogledaj LICENSE fajl za detalje.

## 🤝 Doprinos

Doprinosi su dobrodošli! Molimo:
1. Fork repository
2. Kreiraj feature branch
3. Commit promene
4. Push na branch
5. Otvori Pull Request

## 📞 Podrška

Za pitanja i podršku:
- Otvori Issue na GitHub-u
- Pošalji email na support@example.com
- Pridruži se Discord serveru

---

**🚀 Srećno trgovanje! 📈**