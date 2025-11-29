"""
Configuration management for the trading system.
"""
import os
import json
import yaml
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ExchangeType(str, Enum):
    """Supported exchange types."""
    BINANCE = "binance"
    BITFINEX = "bitfinex"
    KRAKEN = "kraken"
    COINBASE = "coinbase"
    FTX = "ftx"
    BYBIT = "bybit"

@dataclass
class DatabaseConfig:
    """Database configuration."""
    type: str = "sqlite"
    host: str = "localhost"
    port: int = 5432
    name: str = "trading_bot"
    user: str = "postgres"
    password: str = ""
    async_engine: bool = True
    echo: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabaseConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class ExchangeConfig:
    """Exchange API configuration."""
    name: str
    type: ExchangeType
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""  # For exchanges like Coinbase
    sandbox: bool = False
    rate_limit: int = 10  # Requests per second
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExchangeConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class StrategyConfig:
    """Trading strategy configuration."""
    name: str
    enabled: bool = True
    symbols: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_size_pct: float = 10.0  # Max position size as % of equity
    max_risk_per_trade_pct: float = 1.0  # Max risk per trade as % of equity
    max_daily_drawdown_pct: float = 5.0  # Max daily drawdown before stopping
    max_leverage: float = 10.0  # Maximum allowed leverage
    stop_loss_pct: float = 2.0  # Default stop loss percentage
    take_profit_pct: float = 4.0  # Default take profit percentage
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    file: Optional[str] = "trading_bot.log"
    max_size_mb: int = 100  # Max log file size in MB
    backup_count: int = 5  # Number of backup logs to keep
    console: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        """Create from dictionary."""
        if "level" in data and isinstance(data["level"], str):
            data["level"] = LogLevel[data["level"].upper()]
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    enabled: bool = True
    prometheus_port: int = 9090
    metrics_enabled: bool = True
    health_check_enabled: bool = True
    health_check_port: int = 8080
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonitoringConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class NotificationConfig:
    """Notification configuration."""
    email_enabled: bool = False
    email_from: str = ""
    email_to: List[str] = field(default_factory=list)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    
    pagerduty_enabled: bool = False
    pagerduty_integration_key: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    initial_balance: float = 10000.0
    start_date: str = "2023-01-01"
    end_date: str = "2023-12-31"
    timeframe: str = "1d"
    commission: float = 0.001  # 0.1% commission per trade
    slippage: float = 0.0005   # 0.05% slippage per trade
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

@dataclass
class Config:
    """Main configuration class."""
    # Core settings
    name: str = "Crypto Trading Bot"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    
    # Paths
    base_dir: str = str(Path(__file__).parent.parent.parent)
    data_dir: str = "data"
    logs_dir: str = "logs"
    config_dir: str = "config"
    
    # Components
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    
    # Dynamic components
    exchanges: List[ExchangeConfig] = field(default_factory=list)
    strategies: List[StrategyConfig] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization."""
        # Convert string paths to absolute paths
        self.base_dir = str(Path(self.base_dir).resolve())
        self.data_dir = str(Path(self.data_dir).resolve() if os.path.isabs(self.data_dir) else Path(self.base_dir) / self.data_dir)
        self.logs_dir = str(Path(self.logs_dir).resolve() if os.path.isabs(self.logs_dir) else Path(self.base_dir) / self.logs_dir)
        self.config_dir = str(Path(self.config_dir).resolve() if os.path.isabs(self.config_dir) else Path(self.base_dir) / self.config_dir)
        
        # Create directories if they don't exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create configuration from a dictionary."""
        config = cls()
        
        # Update top-level attributes
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # Update nested configurations
        if "database" in data:
            config.database = DatabaseConfig.from_dict(data["database"])
        
        if "logging" in data:
            config.logging = LoggingConfig.from_dict(data["logging"])
        
        if "monitoring" in data:
            config.monitoring = MonitoringConfig.from_dict(data["monitoring"])
        
        if "notifications" in data:
            config.notifications = NotificationConfig.from_dict(data["notifications"])
        
        if "risk" in data:
            config.risk = RiskConfig.from_dict(data["risk"])
        
        if "backtest" in data:
            config.backtest = BacktestConfig.from_dict(data["backtest"])
        
        # Load exchanges
        if "exchanges" in data and isinstance(data["exchanges"], list):
            config.exchanges = [
                ExchangeConfig.from_dict(exchange) 
                for exchange in data["exchanges"]
            ]
        
        # Load strategies
        if "strategies" in data and isinstance(data["strategies"], list):
            config.strategies = [
                StrategyConfig.from_dict(strategy) 
                for strategy in data["strategies"]
            ]
        
        return config
    
    @classmethod
    def from_file(cls, file_path: str) -> 'Config':
        """Load configuration from a file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            if file_path.suffix.lower() == '.json':
                data = json.load(f)
            elif file_path.suffix.lower() in ('.yaml', '.yml'):
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported config file format: {file_path.suffix}")
        
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        data = asdict(self)
        
        # Convert enums to strings
        if isinstance(data["logging"]["level"], LogLevel):
            data["logging"]["level"] = data["logging"]["level"].value
        
        return data
    
    def save(self, file_path: str) -> None:
        """Save configuration to a file."""
        file_path = Path(file_path)
        data = self.to_dict()
        
        with open(file_path, 'w') as f:
            if file_path.suffix.lower() == '.json':
                json.dump(data, f, indent=2)
            elif file_path.suffix.lower() in ('.yaml', '.yml'):
                yaml.dump(data, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported config file format: {file_path.suffix}")
    
    def get_exchange_config(self, exchange_name: str) -> Optional[ExchangeConfig]:
        """Get exchange configuration by name."""
        for exchange in self.exchanges:
            if exchange.name.lower() == exchange_name.lower():
                return exchange
        return None
    
    def get_strategy_config(self, strategy_name: str) -> Optional[StrategyConfig]:
        """Get strategy configuration by name."""
        for strategy in self.strategies:
            if strategy.name.lower() == strategy_name.lower():
                return strategy
        return None

def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file or environment variables.
    
    Args:
        config_path: Path to the configuration file. If None, looks for config in default locations.
        
    Returns:
        Config: Loaded configuration
    """
    # Default config file paths
    default_paths = [
        "config/config.yaml",
        "config/config.json",
        "config.yaml",
        "config.json",
    ]
    
    # If config_path is provided, try to load from that file
    if config_path:
        try:
            return Config.from_file(config_path)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    # Try default paths
    for path in default_paths:
        try:
            if os.path.exists(path):
                return Config.from_file(path)
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")
    
    # If no config file found, return default config
    logger.warning("No configuration file found, using default settings")
    return Config()

# Global config instance
config = load_config()

def update_config(new_config: Union[Dict[str, Any], str, Config]) -> None:
    """
    Update the global configuration.
    
    Args:
        new_config: New configuration as a dictionary, file path, or Config instance
    """
    global config
    
    if isinstance(new_config, str):
        # Load from file
        config = load_config(new_config)
    elif isinstance(new_config, dict):
        # Update from dictionary
        config = Config.from_dict(new_config)
    elif isinstance(new_config, Config):
        # Use provided Config instance
        config = new_config
    else:
        raise ValueError("Invalid configuration type. Expected dict, str, or Config instance.")
    
    logger.info("Configuration updated")
