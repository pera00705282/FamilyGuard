import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from ..utils.config import load_config

logger = logging.getLogger(__name__)

class SecureConfig:
    """Manages secure configuration with environment variable overrides."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(
            Path.home() / '.crypto_trading' / 'config.yaml'
        )
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        try:
            config = load_config(self.config_path)
            self._apply_env_overrides(config)
            self._validate_config(config)
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return {}
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> None:
        for key, value in os.environ.items():
            if key.startswith('CRYPTO_TRADING_'):
                parts = key[len('CRYPTO_TRADING_'):].lower().split('__')
                self._set_nested(config, parts, value)
    
    def _set_nested(self, config: Dict[str, Any], path: list, value: Any) -> None:
        current = config
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[path[-1]] = value
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        if 'exchanges' not in config:
            config['exchanges'] = {}
        
        for exchange, settings in config.get('exchanges', {}).items():
            if 'api_key' in settings and settings['api_key']:
                logger.warning(
                    f"API key found in plain text for {exchange}. "
                    "Consider using environment variables or secure storage."
                )
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self._config, f)
            os.chmod(self.config_path, 0o600)
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

config = SecureConfig()
