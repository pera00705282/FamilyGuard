"""
Base REST client for cryptocurrency exchanges.

This module provides a base implementation for REST API clients that interact with
cryptocurrency exchanges. It includes common functionality like request retries,
rate limiting, and error handling.
"""
import aiohttp
import asyncio
import time
import logging
from typing import Any, Dict, Optional, Type, TypeVar, Union
from decimal import Decimal

from .interfaces import ExchangeError, RateLimitExceeded

logger = logging.getLogger(__name__)
T = TypeVar('T', bound='BaseRestClient')


class BaseRestClient:
    """Base class for REST API clients of cryptocurrency exchanges.

    This class provides common functionality for making HTTP requests to exchange
    APIs, including request signing, rate limiting, and error handling.
    """

    # Default timeout for requests in seconds
    REQUEST_TIMEOUT = 30.0
    # Default base URL for the exchange's API
    BASE_URL = ""
    # Default rate limit in requests per second
    RATE_LIMIT = 10
    # Default retry settings for failed requests
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # Initial delay in seconds
    RETRY_BACKOFF = 2.0  # Exponential backoff factor

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        **kwargs
    ) -> None:
        """Initialize the REST client.

        Args:
            api_key: API key for authentication
            api_secret: API secret for request signing
            session: Optional aiohttp ClientSession to use for requests
            **kwargs: Additional exchange-specific parameters
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self._session = session
        self._last_request_time = 0
        self._rate_limit_semaphore = asyncio.Semaphore(self.RATE_LIMIT)
        self._session_owner = session is None
        self._closed = False

    @classmethod
    async def create(
        cls: Type[T],
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs
    ) -> T:
        """Create and initialize a new client instance.

        This factory method should be used instead of direct instantiation to ensure
        proper async initialization.
        """
        instance = cls(api_key=api_key, api_secret=api_secret, **kwargs)
        if instance._session is None:
            instance._session = aiohttp.ClientSession()
        return instance

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._closed:
            return

        if self._session_owner and self._session is not None:
            await self._session.close()
            self._session = None
        self._closed = True

    def __del__(self) -> None:
        """Ensure resources are cleaned up when the object is garbage collected."""
        if not self._closed and self._session_owner and self._session is not None:
            if self._session.loop.is_running():
                asyncio.create_task(self.close())

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting by sleeping if necessary."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        min_interval = 1.0 / self.RATE_LIMIT

        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

        self._last_request_time = time.monotonic()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_required: bool = False,
        signed: bool = False,
        **kwargs
    ) -> Any:
        """Make an HTTP request to the exchange API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., 'ticker/price')
            params: Query parameters
            data: Request body data
            headers: Additional HTTP headers
            auth_required: Whether authentication is required
            signed: Whether the request should be signed
            **kwargs: Additional arguments for aiohttp.ClientSession.request

        Returns:
            The parsed JSON response

        Raises:
            ExchangeError: If the request fails or returns an error
            RateLimitExceeded: If rate limits are exceeded
        """
        if self._closed:
            raise RuntimeError("Cannot make request: client is closed")

        if auth_required and not (self.api_key and self.api_secret):
            raise ExchangeError("API key and secret are required for this request")

        url = f"{self.BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = headers or {}
        params = params or {}
        data = data or {}

        # Add authentication headers if required
        if auth_required:
            headers.update(self._get_auth_headers(method, endpoint, params, data))

        # Add user agent
        headers.setdefault('User-Agent', 'crypto-trading/1.0')

        # Make the request with retries
        last_exception = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Enforce rate limiting
                async with self._rate_limit_semaphore:
                    await self._enforce_rate_limit()

                    async with self._session.request(
                        method=method,
                        url=url,
                        params=params,
                        json=data if data else None,
                        headers=headers,
                        timeout=self.REQUEST_TIMEOUT,
                        **kwargs
                    ) as response:
                        if response.status == 429:  # Rate limit exceeded
                            retry_after = float(response.headers.get('Retry-After', 5.0))
                            logger.warning(
                                "Rate limit exceeded. Waiting %.1f seconds before retry.",
                                retry_after
                            )
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status >= 400:
                            error_text = await response.text()
                            raise self._create_exchange_error(
                                response.status,
                                error_text,
                                method=method,
                                url=url,
                                params=params,
                                data=data
                            )

                        # Parse JSON response
                        if response.content_type == 'application/json':
                            return await response.json()
                        return await response.text()

            except aiohttp.ClientError as e:
                last_exception = e
                logger.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt + 1, self.MAX_RETRIES + 1, str(e)
                )
                if attempt == self.MAX_RETRIES:
                    break

                # Exponential backoff
                delay = self.RETRY_DELAY * (self.RETRY_BACKOFF ** attempt)
                await asyncio.sleep(delay)

        # If we get here, all retries failed
        if isinstance(last_exception, aiohttp.ClientError):
            raise ExchangeError(f"Request failed: {str(last_exception)}") from last_exception
        raise last_exception or ExchangeError("Request failed")

    def _get_auth_headers(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate authentication headers for a request.

        This method should be implemented by subclasses to provide exchange-specific
        authentication logic.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters
            data: Request body data

        Returns:
            Dictionary of HTTP headers to include in the request
        """
        raise NotImplementedError("Authentication not implemented for this exchange")

    def _create_exchange_error(
        self,
        status_code: int,
        error_text: str,
        **context: Any
    ) -> ExchangeError:
        """Create an appropriate ExchangeError from an API error response.

        Args:
            status_code: HTTP status code
            error_text: Error message from the API
            **context: Additional context about the request

        Returns:
            An ExchangeError or one of its subclasses
        """
        if status_code == 429:
            return RateLimitExceeded("Rate limit exceeded")
        return ExchangeError(f"API error ({status_code}): {error_text}")

    # Common API methods that can be overridden by subclasses

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker information for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            Ticker data
        """
        raise NotImplementedError

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of orders to return

        Returns:
            Order book data
        """
        raise NotImplementedError

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Union[Decimal, float, str],
        price: Optional[Union[Decimal, float, str]] = None,
        **params
    ) -> Dict[str, Any]:
        """Create a new order.

        Args:
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            order_type: Order type (e.g., 'limit', 'market')
            quantity: Order quantity
            price: Order price (required for limit orders)
            **params: Additional order parameters

        Returns:
            Order information
        """
        raise NotImplementedError

    async def get_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Get order information.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Order information
        """
        raise NotImplementedError

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            Cancellation result
        """
        raise NotImplementedError
