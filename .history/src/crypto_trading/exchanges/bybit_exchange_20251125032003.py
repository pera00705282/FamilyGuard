"""



Bybit exchange implementation.
"""
from typing import Dict, List, Optional, Tuple, Any

    BaseExchange,
    Ticker,
    OrderBook,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthenticationError
)

class BybitExchange(BaseExchange):
    """Bybit exchange implementation."""

    BASE_URL = "https://api.bybit.com"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        super().__init__(api_key, api_secret)
        self.name = "bybit"
        self._session = None
        self.recv_window = 5000  # 5 seconds

    async def connect(self) -> None:
        """Initialize connection to Bybit API."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def disconnect(self) -> None:
        """Close connection to Bybit API."""
        if self._session:
            await self._session.close()
            self._session = None

    def _generate_signature(self, timestamp: str, recv_window: str, params: Dict = None) -> str:
        """Generate signature for private API calls."""
        param_str = f"{timestamp}{self.api_key}{recv_window}"

        if params:
            param_str += urlencode(sorted(params.items()))

        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, private: bool = False,
                      params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Send HTTP request to Bybit API."""
        if params is None:
            params = {}

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            'Content-Type': 'application/json'
        }

        if private:
            if not self.api_key or not self.api_secret:
                raise ExchangeAuthenticationError("API key and secret are required for private endpoints")

            timestamp = str(int(time.time() * 1000))
            recv_window = str(self.recv_window)

            # Add required parameters
            params.update({
                'api_key': self.api_key,
                'recv_window': recv_window,
                'timestamp': timestamp
            })

            # Generate signature
            signature = self._generate_signature(timestamp, recv_window, params)
            params['sign'] = signature

            # Add API key to headers
            headers['X-BAPI-API-KEY'] = self.api_key
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-TIMESTAMP'] = timestamp
            headers['X-BAPI-RECV-WINDOW'] = recv_window

        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params if method.upper() == 'GET' else None,
                json=data if method.upper() != 'GET' else None,
                headers=headers
            ) as response:
                result = await response.json()

                if 'ret_code' in result and result['ret_code'] != 0:
                    error_msg = result.get('ret_msg', 'Unknown error')
                    if 'API key' in error_msg and 'invalid' in error_msg:
                        raise ExchangeAuthenticationError(f"Authentication failed: {error_msg}")
                    raise ExchangeError(f"API error: {error_msg}")

                return result.get('result', result)

        except aiohttp.ClientError as e:
            raise ExchangeConnectionError(f"Connection error: {str(e)}")

    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balances."""
        endpoint = "/v2/private/wallet/balance"
        response = await self._request('GET', endpoint, private=True)

        balances = {}
        for currency, data in response.items():
            if currency == 'USDT':  # USDT is the quote currency
                free = Decimal(data.get('available_balance', 0))
                if free > 0:
                    balances[currency] = free

        return balances

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker information for a symbol."""
        endpoint = "/v2/public/tickers"
        symbol = symbol.upper().replace('/', '')
        params = {'symbol': symbol}

        response = await self._request('GET', endpoint, params=params)
        if not response or len(response) == 0:
            raise ExchangeError(f"No ticker data for {symbol}")

        ticker_data = response[0]
        return Ticker(
            symbol=symbol,
            bid=Decimal(ticker_data['bid_price']),
            ask=Decimal(ticker_data['ask_price']),
            last=Decimal(ticker_data['last_price']),
            base_volume=Decimal(ticker_data['volume_24h']),
            quote_volume=Decimal(ticker_data['turnover_24h']),
            timestamp=time.time()
        )

    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        """Get order book for a symbol."""
        endpoint = "/v2/public/orderBook/L2"
        symbol = symbol.upper().replace('/', '')
        params = {
            'symbol': symbol,
            'limit': min(limit, 200)  # Bybit supports up to 200 levels
        }

        response = await self._request('GET', endpoint, params=params)

        # Process order book data
        bids = []
        asks = []

        for item in response:
            price = Decimal(item['price'])
            amount = Decimal(item['size'])
            if item['side'] == 'Buy':
                bids.append((price, amount))
            else:
                asks.append((price, amount))

        # Sort bids (descending) and asks (ascending)
        bids.sort(reverse=True)
        asks.sort()

        return OrderBook(
            bids=bids[:limit],
            asks=asks[:limit],
            timestamp=time.time()
        )

    async def create_order(self, symbol: str, order_type: str, side: str,
                         amount: Decimal, price: Optional[Decimal] = None) -> Dict[str, Any]:
        """Create a new order."""
        endpoint = "/private/linear/order/create"
        symbol = symbol.upper().replace('/', '')

        data = {
            'symbol': symbol,
            'side': side.capitalize(),
            'order_type': order_type.capitalize(),
            'qty': str(amount),
            'time_in_force': 'GoodTillCancel',
            'reduce_only': False,
            'close_on_trigger': False
        }

        if order_type.lower() == 'limit':
            if price is None:
                raise ValueError("Price is required for limit orders")
            data['price'] = str(price)
        else:
            data['time_in_force'] = 'ImmediateOrCancel'

        return await self._request('POST', endpoint, private=True, data=data)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of open orders."""
        endpoint = "/private/linear/order/list"
        params = {
            'order_status': 'New,PartiallyFilled,PendingCancel,Created,NewIns,PartiallyFill',
            'limit': 50  # Max limit per request
        }

        if symbol:
            params['symbol'] = symbol.upper().replace('/', '')

        return await self._request('GET', endpoint, private=True, params=params)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        endpoint = "/private/linear/order/cancel"

        try:
            await self._request('POST', endpoint, private=True, data={
                'symbol': symbol.upper().replace('/', ''),
                'order_id': order_id
            })
            return True
        except ExchangeError:
            return False

    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get list of available markets and their details."""
        endpoint = "/v2/public/symbols"
        response = await self._request('GET', endpoint)

        markets = []
        for market in response:
            if market['status'] == 'Trading':  # Only include active markets
                markets.append({
                    'symbol': market['name'],
                    'base': market['base_currency'],
                    'quote': market['quote_currency'],
                    'precision': {
                        'price': market['price_scale'],
                        'amount': market['lot_size_filter']['qty_step'].count('0')
                    },
                    'min_amount': Decimal(market['lot_size_filter']['min_trading_qty']),
                    'min_total': Decimal(market['lot_size_filter'].get('min_turnover', '0'))
                })

        return markets