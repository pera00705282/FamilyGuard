"""
Security module for the Crypto Trading library.

This module provides security-related functionality including:
- Secure API key management
- Request signing and validation
- Rate limiting
- Secure configuration
"""

from .key_manager import SecureKeyManager, key_manager
from .request_signer import RequestSigner
from .rate_limiter import RateLimiter
from .middleware import SecurityMiddleware
from .config import SecureConfig, config

__all__ = [
    'SecureKeyManager',
    'key_manager',
    'RequestSigner',
    'RateLimiter',
    'SecurityMiddleware',
    'SecureConfig',
    'config'
]
