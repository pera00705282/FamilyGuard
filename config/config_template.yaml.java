# Crypto Trading Automation Configuration
# =====================================

# Exchange Configuration
exchanges:
  binance:
    api_key: "YOUR_BINANCE_API_KEY"
    secret: "YOUR_BINANCE_SECRET"
    sandbox: true  # Set to false for live trading
    rate_limit: 1200  # requests per minute
    enable_rate_limit: true
    timeout: 30000
    
  coinbase:
    api_key: "YOUR_COINBASE_API_KEY"
    secret: "YOUR_COINBASE_SECRET"
    passphrase: "YOUR_COINBASE_PASSPHRASE"
    sandbox: true  # Set to false for live trading
    rate_limit: 10  # requests per second
    enable_rate_limit: true
    timeout: 30000
    
  kraken:
    api_key: "YOUR_KRAKEN_API_KEY"
    secret: "YOUR_KRAKEN_SECRET"
    sandbox: false  # Kraken doesn't have sandbox
    rate_limit: 15  # calls per minute
    enable_rate_limit: true
    timeout: 30000

# Trading Configuration
trading:
  # Trading pairs to monitor and trade
  symbols:
    - "BTC/USDT"
    - "ETH/USDT"
    - "ADA/USDT"
    - "DOT/USDT"
    - "LINK/USDT"
  
  # Base currency for calculations
  base_currency: "USDT"
  
  # Risk Management
  risk_management:
    max_position_size: 0.1        # 10% of portfolio per position
    stop_loss_pct: 0.02           # 2% stop loss
    take_profit_pct: 0.05         # 5% take profit
    risk_per_trade: 0.01          # 1% risk per trade
    max_daily_trades: 10          # Maximum trades per day
    max_portfolio_risk: 0.1       # 10% maximum portfolio risk
    max_drawdown: 0.15            # 15% maximum drawdown
    max_correlation: 0.7          # Maximum correlation between positions
  
  # Trading Strategy
  strategy:
    type: "multi_strategy"        # conservative, aggressive, scalping, multi_strategy
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
      - name: "macd"
        weight: 0.25
        params:
          fast_period: 12
          slow_period: 26
          signal_period: 9
      - name: "bollinger_bands"
        weight: 0.2
        params:
          period: 20
          std_dev: 2.0
  
  # Order Configuration
  orders:
    default_type: "limit"         # market, limit
    slippage_tolerance: 0.001     # 0.1% slippage tolerance
    retry_attempts: 3             # Number of retry attempts
    retry_delay: 5                # Seconds between retries

# Portfolio Configuration
portfolio:
  initial_balance: 10000.0        # Starting balance in base currency
  save_state_interval: 300       # Save portfolio state every 5 minutes
  state_file: "portfolio_state.json"

# Monitoring and Alerting
monitoring:
  enable_live_console: true       # Enable live console monitoring
  enable_web_dashboard: true      # Enable web dashboard
  dashboard_port: 8080           # Web dashboard port
  
  # Metrics collection
  metrics:
    collection_interval: 30       # Seconds between metric collections
    retention_hours: 168          # Keep metrics for 7 days
    
  # Alert Configuration
  alerts:
    enable_email: false
    enable_telegram: false
    enable_webhook: false
    
    # Email settings (if enabled)
    email:
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      username: "your_email@gmail.com"
      password: "your_app_password"
      from_email: "your_email@gmail.com"
      to_emails:
        - "alert@example.com"
    
    # Telegram settings (if enabled)
    telegram:
      bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
      chat_ids:
        - "YOUR_CHAT_ID"
    
    # Webhook settings (if enabled)
    webhook:
      urls:
        - "https://your-webhook-url.com/alerts"
  
  # Alert Rules
  alert_rules:
    - metric: "drawdown_pct"
      condition: "gt"
      threshold: 10.0
      level: "warning"
      message: "Portfolio drawdown exceeded 10%"
    
    - metric: "drawdown_pct"
      condition: "gt"
      threshold: 20.0
      level: "critical"
      message: "Portfolio drawdown exceeded 20%"
    
    - metric: "daily_pnl_pct"
      condition: "lt"
      threshold: -5.0
      level: "warning"
      message: "Daily PnL below -5%"
    
    - metric: "api_error_rate"
      condition: "gt"
      threshold: 0.1
      level: "error"
      message: "API error rate too high"

# WebSocket Configuration
websocket:
  enable_feeds: true              # Enable real-time WebSocket feeds
  reconnect_attempts: 5           # Number of reconnection attempts
  reconnect_delay: 10             # Seconds between reconnection attempts
  
  # Feed configuration
  feeds:
    trades: true                  # Enable trade feeds
    tickers: true                 # Enable ticker feeds
    orderbooks: true              # Enable order book feeds
    funding: false                # Enable funding rate feeds
    open_interest: false          # Enable open interest feeds

# Logging Configuration
logging:
  level: "INFO"                   # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: "crypto_trading.log"
  max_file_size: "10MB"
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Security Configuration
security:
  encrypt_api_keys: false         # Encrypt API keys in config (requires password)
  api_key_rotation_days: 90       # Rotate API keys every 90 days
  enable_ip_whitelist: true       # Enable IP whitelisting on exchanges
  
# Development and Testing
development:
  enable_backtesting: false       # Enable backtesting mode
  backtest_start_date: "2023-01-01"
  backtest_end_date: "2023-12-31"
  paper_trading: true             # Enable paper trading (no real orders)
  
# Advanced Configuration
advanced:
  # Database configuration (optional)
  database:
    enable: false
    type: "sqlite"                # sqlite, postgresql, mysql
    url: "sqlite:///trading.db"
  
  # Redis configuration (optional)
  redis:
    enable: false
    host: "localhost"
    port: 6379
    db: 0
  
  # Performance optimization
  performance:
    enable_caching: true
    cache_ttl: 60                 # Cache TTL in seconds
    max_concurrent_requests: 10   # Maximum concurrent API requests
    
  # Machine Learning (experimental)
  ml:
    enable_predictions: false
    model_type: "lstm"            # lstm, transformer, ensemble
    retrain_interval: 24          # Hours between model retraining
    prediction_horizon: 4         # Hours to predict ahead

# IMPORTANT SETTINGS
# ==================

# Set this to true ONLY when you're ready for real trading with real money!
enable_live_trading: false

# Trading mode: "paper", "live"
trading_mode: "paper"

# Confirmation required for live trading
require_trading_confirmation: true