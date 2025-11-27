"""



HTTP client for making asynchronous API requests to exchanges.
"""
from typing import Any, Dict, Optional, Tuple, Union


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, rate_limit: int, time_window: float = 60.0):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum number of requests allowed in the time window
            time_window: Time window in seconds (default: 60s)
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.timestamps = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a request slot, waiting if necessary to respect rate limits."""
        async with self._lock:
            now = time.time()

            # Remove timestamps older than the time window
            self.timestamps = [t for t in self.timestamps if now - t < self.time_window]

            if len(self.timestamps) >= self.rate_limit:
                # Calculate sleep time to respect rate limit
                sleep_time = self.timestamps[0] + self.time_window - now
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                # Update timestamps after sleep
                now = time.time()
                self.timestamps = [t for t in self.timestamps[1:] if now - t < self.time_window]

            self.timestamps.append(now)


class HttpClient:
    """Asynchronous HTTP client for exchange APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        api_secret: str = "",
        rate_limit: int = 10,
        timeout: int = 30,
        retries: int = 3,
    ):
        """
        Initialize the HTTP client.

        Args:
            base_url: Base URL for the API
            api_key: API key for authentication
            api_secret: API secret for signing requests
            rate_limit: Maximum number of requests per minute
            timeout: Request timeout in seconds
            retries: Number of retries for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.retries = max(1, retries)
        self.rate_limiter = RateLimiter(rate_limit)
        self.session = None
        self._logger = logging.getLogger(self.__class__.__name__)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp client session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                json_serialize=json.dumps
            )
        return self.session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        """
        Sign the payload with the API secret.

        Args:
            payload: The payload to sign

        Returns:
            Hex-encoded signature
        """
        if not self.api_secret:
            return ""

        query_string = '&'.join([f"{k}={v}" for k, v in sorted(payload.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _prepare_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: bool = False
    ) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Prepare the request URL, params, and headers.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            headers: Additional headers
            auth: Whether to include authentication

        Returns:
            Tuple of (url, params, headers)
        """
        # Ensure params and headers are dicts
        params = params or {}
        headers = headers or {}

        # Add authentication if required
        if auth and self.api_key:
            if method.upper() == 'GET':
                # For GET requests, add auth to query params
                params['api_key'] = self.api_key
                params['timestamp'] = int(time.time() * 1000)
                params['signature'] = self._sign_payload(params)
            else:
                # For other methods, add auth to headers
                headers['X-MBX-APIKEY'] = self.api_key

        # Build URL
        url = f"{self.base_url}{endpoint}"

        # Add query parameters for GET requests
        if method.upper() == 'GET' and params:
            url = f"{url}?{urlencode(params, doseq=True)}"

        return url, params, headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: bool = False,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            headers: Additional headers
            auth: Whether to include authentication
            retry_count: Current retry attempt

        Returns:
            Parsed JSON response

        Raises:
            aiohttp.ClientError: If the request fails after all retries
        """
        # Wait for rate limit
        await self.rate_limiter.acquire()

        # Prepare request
        url, params, headers = self._prepare_request(
            method, endpoint, params, data, headers, auth
        )

        # Make the request
        session = await self._get_session()

        try:
            self._logger.debug(
                "%s %s (attempt %d/%d)",
                method.upper(),
                url,
                retry_count + 1,
                self.retries
            )

            async with session.request(
                method,
                url,
                params=params if method.upper() != 'GET' else None,
                json=data if method.upper() != 'GET' else None,
                headers=headers
            ) as response:
                # Handle error responses
                if response.status >= 400:
                    text = await response.text()
                    self._logger.error(
                        "HTTP %d: %s",
                        response.status,
                        text[:200]  # Log first 200 chars to avoid huge logs
                    )

                    # Retry on server errors and rate limits
                    if response.status >= 500 or response.status == 429:
                        if retry_count < self.retries - 1:
                            backoff = 2 ** retry_count  # Exponential backoff
                            await asyncio.sleep(backoff)
                            return await self.request(
                                method,
                                endpoint,
                                params=params,
                                data=data,
                                headers=headers,
                                auth=auth,
                                retry_count=retry_count + 1
                            )

                    # Raise exception for client errors
                    raise aiohttp.ClientError(
                        f"HTTP {response.status}: {text}"
                    )

                # Parse and return JSON response
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self._logger.error("Request failed: %s", str(e))

            # Retry on connection errors
            if retry_count < self.retries - 1:
                backoff = 2 ** retry_count  # Exponential backoff
                await asyncio.sleep(backoff)
                return await self.request(
                    method,
                    endpoint,
                    params=params,
                    data=data,
                    headers=headers,
                    auth=auth,
                    retry_count=retry_count + 1
                )

            raise

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a GET request."""
        return await self.request('GET', endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a POST request."""
        return await self.request('POST', endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a PUT request."""
        return await self.request('PUT', endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a DELETE request."""
        return await self.request('DELETE', endpoint, **kwargs)