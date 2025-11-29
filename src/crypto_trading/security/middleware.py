"""
Security Middleware Module

This module provides middleware for adding security features to HTTP requests,
including rate limiting, request signing, and error handling.
"""
import logging
from typing import Any, Optional

from aiohttp import ClientRequest, ClientResponse, ClientSession, ClientTimeout

from ..exceptions import AuthenticationError, RateLimitExceeded

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Middleware for adding security features to HTTP requests."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        rate_limiter: Optional[Any] = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limiter = rate_limiter
        self.request_signer = None
        
        if api_key and api_secret:
            from .request_signer import RequestSigner
            self.request_signer = RequestSigner(api_key, api_secret)
    
    async def __call__(
        self,
        request: ClientRequest,
        session: ClientSession,
        **kwargs
    ) -> ClientResponse:
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        if self.request_signer:
            headers = self.request_signer.sign_request(
                method=request.method,
                url=str(request.url),
                params=dict(request.url.query),
                data=request._body if hasattr(request, '_body') else None,
                headers=dict(request.headers)
            )
            request.headers.update(headers)
        
        request.headers.setdefault('User-Agent', 'Crypto-Trading/1.0')
        request.headers.setdefault('Accept', 'application/json')
        
        if 'timeout' not in kwargs:
            kwargs['timeout'] = ClientTimeout(total=30)
        
        try:
            response = await session._request(
                request.method,
                request.url,
                headers=request.headers,
                data=request._body,
                **kwargs
            )

            if response.status == 429:
                retry_after = float(response.headers.get('Retry-After', 5))
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Retry after {retry_after} seconds",
                    retry_after=retry_after
                )

            if response.status == 401:
                raise AuthenticationError("Invalid API key or signature")

            return response

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
