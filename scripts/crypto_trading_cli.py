"""Configuration utilities"""

import yaml
from typing import Dict, Optional
from pydantic import BaseModel, field_validator
import logging

logger = logging.getLogger(__name__)


class ExchangeConfig(BaseModel):
    """Exchange configuration model"""

    api_key: str
    secret: str
    passphrase: Optional[str] = None
    sandbox: bool = True
    rate_limit: int = 100
    enable_rate_limit: bool = True


class TradingConfig(BaseModel):
    """Trading configuration model"""

    symbols: list = ["BTC/USDT", "ETH/USDT"]
    strategies: list = ["conservative"]
    max_positions: int = 5

    class RiskManagement(BaseModel):
        max_position_size: float = 0.1
        stop_loss_pct: float = 0.02
        take_profit_pct: float = 0.04
        max_daily_trades: int = 20
        max_drawdown_pct: float = 0.15

    risk_management: RiskManagement = RiskManagement()


class MonitoringConfig(BaseModel):
    """Monitoring configuration model"""

    enable_alerts: bool = True
    alert_channels: list = ["console"]
    metrics_retention_hours: int = 168  # 1 week

    class Email(BaseModel):
        smtp_server: str = "smtp.gmail.com"
        smtp_port: int = 587
        username: str = ""
        password: str = ""
        to_addresses: list = []

    class Telegram(BaseModel):
        bot_token: str = ""
        chat_ids: list = []

    email: Email = Email()
    telegram: Telegram = Telegram()


class Config(BaseModel):
    """Main configuration model"""

    exchanges: Dict[str, ExchangeConfig]
    trading: TradingConfig = TradingConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    enable_live_trading: bool = False
    log_level: str = "INFO"

    @field_validator("exchanges")
    @classmethod
    def validate_exchanges(cls, v: Dict[str, ExchangeConfig]) -> Dict[str, ExchangeConfig]:
        if not v:
            raise ValueError("At least one exchange must be configured")
        return v


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file"""
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        return Config(**config_data)

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def save_config(config: Config, config_path: str):
    """Save configuration to YAML file"""
    try:
        config_dict = config.dict()

        with open(config_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

        logger.info(f"Configuration saved to {config_path}")

    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise


def create_default_config() -> Config:
    """Create default configuration"""
    return Config(
        exchanges={
            "binance": ExchangeConfig(
                api_key="YOUR_BINANCE_API_KEY", secret="YOUR_BINANCE_SECRET", sandbox=True
            ),
            "coinbase": ExchangeConfig(
                api_key="YOUR_COINBASE_API_KEY",
                secret="YOUR_COINBASE_SECRET",
                passphrase="YOUR_COINBASE_PASSPHRASE",
                sandbox=True,
            ),
            "kraken": ExchangeConfig(
                api_key="YOUR_KRAKEN_API_KEY", secret="YOUR_KRAKEN_SECRET", sandbox=True
            ),
        }
    )
