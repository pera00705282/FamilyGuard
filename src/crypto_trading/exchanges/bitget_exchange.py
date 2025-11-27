"""



Bitget exchange implementation.
"""
from typing import Dict, List, Optional, Tuple, Any, Union

    BaseExchange,
    Ticker,
    OrderBook,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthenticationError
)

class BitgetExchange(BaseExchange):
    """Bitget exchange implementation."""

    BASE_URL = "https://api.bitget.com"

    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = ""):
        """Initialize Bitget exchange.

        Args:
            api_key: Bitget API key
            api_secret: Bitget API secret
            passphrase: Bitget API passphrase (required for private endpoints)
        """
        super().__init__(api_key, api_secret)
        self.name = "bitget"
        self._session = None
        self.passphrase = passphrase
        self.recv_window = 5000  # 5 seconds

    async def connect(self) -> None:
        """Initialize connection to Bitget API."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def disconnect(self) -> None:
        """Close connection to Bitget API."""
        if self._session:
            await self._session.close()
            self._session = None

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """Generate signature for private API calls."""
        if not self.api_secret:
            raise ExchangeAuthenticationError("API secret is required for private endpoints")

        message = timestamp + method.upper() + request_path
        if body:
            message += body

        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _get_headers(self, sign_required: bool = False, method: str = 'GET', request_path: str = '', body: str = '') -> Dict[str, str]:
        """Get request headers."""
        headers = {
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }

        if sign_required:
            if not self.api_key or not self.passphrase:
                raise ExchangeAuthenticationError("API key and passphrase are required for private endpoints")

            timestamp = str(int(time.time() * 1000))
            signature = self._generate_signature(timestamp, method, request_path, body)

            headers.update({
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.passphrase
            })

        return headers

    async def _request(self, method: str, endpoint: str, private: bool = False,
                      params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Send HTTP request to Bitget API."""
        if params is None:
            params = {}

        url = f"{self.BASE_URL}{endpoint}"

        # Convert params to query string for GET requests
        query_string = urlencode(params) if method.upper() == 'GET' and params else ''
        if query_string:
            url = f"{url}?{query_string}"

        # Prepare request body
        body = json.dumps(data) if data else ''

        # Get headers
        headers = self._get_headers(
            sign_required=private,
            method=method.upper(),
            request_path=endpoint + (f"?{query_string}" if query_string else ''),
            body=body
        )

        try:
            async with self._session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=data if method.upper() != 'GET' else None,
                params=params if method.upper() == 'GET' else None
            ) as response:
                result = await response.json()

                if 'code' in result and result['code'] != '0':
                    error_msg = result.get('msg', 'Unknown error')
                    if 'Invalid API Key' in error_msg:
                        raise ExchangeAuthenticationError(f"Authentication failed: {error_msg}")
                    raise ExchangeError(f"API error: {error_msg}")

                return result.get('data', result)

        except aiohttp.ClientError as e:
            raise ExchangeConnectionError(f"Connection error: {str(e)}")

    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balances."""
        endpoint = "/api/spot/v1/account/assets"
        response = await self._request('GET', endpoint, private=True)

        balances = {}
        for asset in response:
            free = Decimal(asset.get('available', '0'))
            if free > 0:
                balances[asset['coinName']] = free

        return balances

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker information for a symbol."""
        endpoint = "/api/spot/v1/market/ticker"
        symbol = symbol.upper().replace('/', '')
        params = {'symbol': symbol}

        response = await self._request('GET', endpoint, params=params)

        return Ticker(
            symbol=symbol,
            bid=Decimal(response.get('bestBid', 0)),
            ask=Decimal(response.get('bestAsk', 0)),
            last=Decimal(response.get('lastPr', 0)),
            base_volume=Decimal(response.get('baseVol', 0)),
            quote_volume=Decimal(response.get('quoteVol', 0)),
            timestamp=time.time()
        )

    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        """Get order book for a symbol."""
        endpoint = "/api/spot/v1/market/orderbook"
        symbol = symbol.upper().replace('/', '')
        params = {
            'symbol': symbol,
            'limit': min(limit, 200)  # Bitget supports up to 200 levels
        }

        response = await self._request('GET', endpoint, params=params)

        # Process order book data
        bids = [(Decimal(price), Decimal(amount)) for price, amount in response['bids'][:limit]]
        asks = [(Decimal(price), Decimal(amount)) for price, amount in response['asks'][:limit]]

        return OrderBook(
            bids=sorted(bids, reverse=True),
            asks=sorted(asks),
            timestamp=time.time()
        )

    async def create_order(self, symbol: str, order_type: str, side: str,
                         amount: Decimal, price: Optional[Decimal] = None) -> Dict[str, Any]:
        """Create a new order."""
        endpoint = "/api/spot/v1/trade/orders"
        symbol = symbol.upper().replace('/', '')

        data = {
            'symbol': symbol,
            'side': side.lower(),
            'orderType': order_type.lower(),
            'force': 'normal',  # normal, ioc, fok
            'size': str(amount)
        }

        if order_type.lower() == 'limit':
            if price is None:
                raise ValueError("Price is required for limit orders")
            data['price'] = str(price)

        return await self._request('POST', endpoint, private=True, data=data)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of open orders."""
        endpoint = "/api/spot/v1/trade/open-orders"
        params = {}

        if symbol:
            params['symbol'] = symbol.upper().replace('/', '')

        return await self._request('GET', endpoint, private=True, params=params)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        endpoint = "/api/spot/v1/trade/cancel-order"

        try:
            await self._request('POST', endpoint, private=True, data={
                'orderId': order_id,
                'symbol': symbol.upper().replace('/', '')
            })
            return True
        except ExchangeError:
            return False

    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get list of available markets and their details."""
        endpoint = "/api/spot/v1/public/products"
        response = await self._request('GET', endpoint)

        markets = []
        for market in response:
            if market['status'] == 'online':  # Only include active markets
                markets.append({
                    'symbol': market['symbol'],
                    'base': market['baseCoin'],
                    'quote': market['quoteCoin'],
                    'precision': {
                        'price': market['priceScale'],
                        'amount': market['quantityScale']
                    },
                    'min_amount': Decimal(market.get('minTradeAmount', '0')),
                    'min_total': Decimal(market.get('minTradeUSDT', '0'))
                })

        return markets