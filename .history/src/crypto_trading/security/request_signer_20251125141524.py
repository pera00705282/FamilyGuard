import hmac
import hashlib
import time
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RequestSigner:
    """Handles request signing for API authentication."""
    
    def __init__(self, api_key: str = '', api_secret: str = ''):
        self.api_key = api_key
        self.api_secret = api_secret.encode() if api_secret else b''
        
    def sign_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, str]:
        if not self.api_key or not self.api_secret:
            return {}
            
        timestamp = timestamp or int(time.time() * 1000)
        headers = headers or {}
        params = params or {}
        data = data or {}
        
        signature_payload = self._create_signature_payload(method, url, params, data, timestamp)
        signature = self._generate_signature(signature_payload)
        
        return {
            'X-API-KEY': self.api_key,
            'X-TIMESTAMP': str(timestamp),
            'X-SIGNATURE': signature,
            **headers
        }
    
    def _create_signature_payload(
        self,
        method: str,
        url: str,
        params: Dict[str, Any],
        data: Dict[str, Any],
        timestamp: int
    ) -> str:
        normalized_url = url.split('?')[0].split('#')[0]
        sorted_params = '&'.join(
            f"{k}={v}" for k, v in sorted(params.items())
        ) if params else ''
        
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True) if data else ''
        else:
            data_str = str(data)
            
        payload_parts = [
            method.upper(),
            normalized_url,
            sorted_params,
            data_str,
            str(timestamp)
        ]
        
        return '|'.join(filter(None, payload_parts))
    
    def _generate_signature(self, payload: str) -> str:
        return hmac.new(
            self.api_secret,
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature_header: str,
        secret: Optional[str] = None
    ) -> bool:
        secret = secret or self.api_secret
        if not secret:
            return False
            
        expected_signature = hmac.new(
            secret.encode() if isinstance(secret, str) else secret,
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature_header)
