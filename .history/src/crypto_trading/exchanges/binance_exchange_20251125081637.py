"""Binance Exchange API client implementation.

This module provides a complete implementation of the Binance REST API client,
including authentication, request signing, and response parsing.
"""
import hmac
import hashlib
import time
import aiohttp
from typing import Any, Dict, List, Optional
from decimal import Decimal

from .base_rest import BaseRestClient
from .interfaces import ExchangeError, TickerData, OrderBookData


class BinanceExchangeClient(BaseRestClient):
    """Binance REST API client implementation.

    This class provides methods to interact with the Binance REST API,
    including market data, account information, and order management.
    """

    # Binance API endpoints
    BASE_URL = "https://api.binance.com"
    TESTNET_URL = "https://testnet.binance.vision"
    # API version
    API_VERSION = "v3"
    # Rate limits (requests per minute)
    RATE_LIMIT = 1200  # 1200 requests per minute by default for verified accounts
    # Endpoints
    ENDPOINTS = {
        'exchange_info': '/api/v3/exchangeInfo',
        'ticker_24h': '/api/v3/ticker/24hr',
        'ticker_price': '/api/v3/ticker/price',
        'order_book': '/api/v3/depth',
        'recent_trades': '/api/v3/trades',
        'create_order': '/api/v3/order',
        'get_order': '/api/v3/order',
        'cancel_order': '/api/v3/order',
        'open_orders': '/api/v3/openOrders',
        'account': '/api/v3/account',
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        **kwargs
    ) -> None:
        """Initialize the Binance API client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Whether to use the testnet environment
            **kwargs: Additional arguments for BaseRestClient
        """
        self.testnet = testnet
        if testnet:
            self.BASE_URL = self.TESTNET_URL

        super().__init__(api_key=api_key, api_secret=api_secret, **kwargs)

        # Cache for exchange info to avoid repeated API calls
        self._exchange_info = None
        self._exchange_info_loaded = False

    async def connect(self) -> None:
        """Initialize connection to Binance API."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def disconnect(self) -> None:
        """Close connection to Binance API."""
        if self._session:
            await self._session.close()
            self._session = None

        if self._ws:
            await self._ws.close()
            self._ws = None

    def _generate_signature(self, data: Dict) -> str:
        """Generate signature for private API calls."""
        query_string = '&'.join([f"{k}={v}" for k, v in data.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(
        self,
        method: str,
        endpoint: str,
        private: bool = False,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """Send HTTP request to Binance API."""
        if params is None:
            params = {}

        if private:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)

        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params if method.upper() == 'GET' else None,
                data=params if method.upper() != 'GET' else None,
                headers={"X-MBX-APIKEY": self.api_key} if private else {}
            ) as response:
                result = await response.json()

                if 'code' in result and result['code'] != 0:
                    error_msg = result.get('msg', 'Unknown error')
                    if result['code'] == -2015 or result['code'] == -2014:
                        raise ExchangeError(f"Authentication failed: {error_msg}")
                    raise ExchangeError(f"API error {result['code']}: {error_msg}")

                return result

        except aiohttp.ClientError as e:
            raise ExchangeError(f"Connection error: {str(e)}")

    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balances."""
        endpoint = "/api/v3/account"
        response = await self._request('GET', endpoint, private=True)

        balances = {}
        for asset in response['balances']:
            free = Decimal(asset['free'])
            locked = Decimal(asset['locked'])
            if free > 0 or locked > 0:
                balances[asset['asset']] = free

        return balances

    async def get_ticker(self, symbol: str) -> TickerData:
        """Get ticker information for a symbol."""
        endpoint = "/api/v3/ticker/bookTicker"
        params = {'symbol': symbol.upper().replace('/', '')}

        response = await self._request('GET', endpoint, params=params)

        return TickerData(
            symbol=symbol,
            bid=Decimal(response['bidPrice']),
            ask=Decimal(response['askPrice']),
            last=Decimal(response['bidPrice']),  # Best we can do with this endpoint
            base_volume=Decimal('0'),  # Not available in this endpoint
            quote_volume=Decimal('0'),  # Not available in this endpoint
            timestamp=time.time()
        )

    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBookData:
        """Get order book for a symbol."""
        endpoint = "/api/v3/depth"
        params = {
            'symbol': symbol.upper().replace('/', ''),
            'limit': min(limit, 5000)  # Binance supports up to 5000 levels
        }

        response = await self._request('GET', endpoint, params=params)

        return OrderBookData(
            bids=[(Decimal(price), Decimal(amount)) for price, amount in response['bids']],
            asks=[(Decimal(price), Decimal(amount)) for price, amount in response['asks']],
            timestamp=response['lastUpdateId']
        )

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Create a new order."""
        endpoint = "/api/v3/order"

        params = {
            'symbol': symbol.upper().replace('/', ''),
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': str(amount),
            'newOrderRespType': 'FULL'  # Get full order details in response
        }

        if order_type.lower() == 'limit':
            if price is None:
                raise ValueError("Price is required for limit orders")
            params['timeInForce'] = 'GTC'  # Good Till Cancelled
            params['price'] = str(price)

        response = await self._request('POST', endpoint, private=True, params=params)
        return response

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of open orders."""
        endpoint = "/api/v3/openOrders"
        params = {}

        if symbol:
            params['symbol'] = symbol.upper().replace('/', '')

        return await self._request('GET', endpoint, private=True, params=params)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        endpoint = "/api/v3/order"
        params = {
            'symbol': symbol.upper().replace('/', ''),
            'orderId': order_id
        }

        try:
            await self._request('DELETE', endpoint, private=True, params=params)
            return True
        except ExchangeError:
            return False

    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get list of available markets and their details."""
        endpoint = "/api/v3/exchangeInfo"
        response = await self._request('GET', endpoint)

        markets = []
        for symbol in response['symbols']:
            if symbol['status'] == 'TRADING':  # Only include active markets
                markets.append({
                    'symbol': symbol['symbol'],
                    'base': symbol['baseAsset'],
                    'quote': symbol['quoteAsset'],
                    'precision': {
                        'price': symbol['quotePrecision'],
                        'amount': symbol['baseAssetPrecision']
                    },
                    'filters': symbol.get('filters', [])
                })

        return markets
