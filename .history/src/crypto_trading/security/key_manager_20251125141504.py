import os
import base64
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class SecureKeyManager:
    """Manages secure storage and retrieval of API keys using encryption."""
    
    def __init__(self, key_file: str = None, password: Optional[str] = None):
        self.key_file = key_file or str(Path.home() / '.crypto_trading' / 'keys.enc')
        self.password = password or os.getenv('CRYPTO_TRADING_KEY_PASSWORD', '')
        self.keys = {}
        self._fernet = None
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        self._init_fernet()
        self._load_keys()

    def _init_fernet(self) -> None:
        salt = b'crypto_trading_salt'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
        self._fernet = Fernet(key)

    def _load_keys(self) -> None:
        try:
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    encrypted_data = f.read()
                    if encrypted_data:
                        decrypted_data = self._fernet.decrypt(encrypted_data)
                        self.keys = json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")
            self.keys = {}

    def _save_keys(self) -> None:
        try:
            data = json.dumps(self.keys).encode()
            encrypted_data = self._fernet.encrypt(data)
            with open(self.key_file, 'wb') as f:
                f.write(encrypted_data)
            os.chmod(self.key_file, 0o600)
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")

    def store_key(self, exchange: str, api_key: str, api_secret: str) -> None:
        self.keys[exchange.lower()] = {
            'api_key': api_key,
            'api_secret': api_secret,
            'updated_at': int(time.time())
        }
        self._save_keys()

    def get_key(self, exchange: str) -> Optional[Dict[str, str]]:
        return self.keys.get(exchange.lower())

    def delete_key(self, exchange: str) -> bool:
        if exchange.lower() in self.keys:
            del self.keys[exchange.lower()]
            self._save_keys()
            return True
        return False

    def rotate_keys(self, exchange: str, new_api_key: str, new_api_secret: str) -> None:
        self.store_key(exchange, new_api_key, new_api_secret)
        logger.info(f"Rotated API keys for {exchange}")

key_manager = SecureKeyManager()
