"""



Bitfinex exchange implementation.
"""
from typing import Any, Dict, List, Optional, Tuple, Union

    BaseExchange,
    Ticker,
    OrderBook,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthenticationError
)

class BitfinexExchange(BaseExchange):
    """Bitfinex exchange implementation."""

    BASE_URL = "https://api.bitfinex.com/v2"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        """Initialize Bitfinex exchange.

        Args:
            api_key: Bitfinex API key
            api_secret: Bitfinex API secret
        """
        super().__init__(api_key, api_secret)
        self.name = "bitfinex"
        self._session = None
        self._nonce = int(time.time() * 1000)

    async def connect(self) -> None:
        """Initialize connection to Bitfinex API."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def disconnect(self) -> None:
        """Close connection to Bitfinex API."""
        if self._session:
            await self._session.close()
            self._session = None

    def _get_auth_headers(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, str]:
        """Generate authentication headers for private API calls."""
        if not self.api_key or not self.api_secret:
            raise ExchangeAuthenticationError("API key and secret are required for private endpoints")

        self._nonce = str(int(self._nonce) + 1)

        if data is None:
            data = {}

        data = {
            "request": f"/v2{endpoint}",
            "nonce": self._nonce,
            **data
        }

        payload = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha384
        ).hexdigest()

        return {
            'bfx-nonce': self._nonce,
            'bfx-apikey': self.api_key,
            'bfx-signature': signature,
            'content-type': 'application/json'
        }

    async def _request(self, method: str, endpoint: str, private: bool = False,
                      params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Send HTTP request to Bitfinex API."""
        if params is None:
            params = {}

        url = f"{self.BASE_URL}{endpoint}"
        headers = {}

        if private:
            headers.update(self._get_auth_headers(endpoint, data))

        try:
            async with self._session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=data if method.upper() != 'GET' else None
            ) as response:
                result = await response.json()

                if isinstance(result, dict) and 'error' in result:
                    error_msg = result.get('message', 'Unknown error')
                    if 'apikey' in error_msg.lower():
                        raise ExchangeAuthenticationError(f"Authentication failed: {error_msg}")
                    raise ExchangeError(f"API error: {error_msg}")

                return result

        except aiohttp.ClientError as e:
            raise ExchangeConnectionError(f"Connection error: {str(e)}")

    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balances."""
        endpoint = "/auth/r/wallets"
        response = await self._request('POST', endpoint, private=True)

        balances = {}
        for wallet in response:
            if wallet[0] == 'exchange':  # Only include exchange wallet
                currency = wallet[1].upper()
                free = Decimal(str(wallet[2]))
                if free > 0:
                    balances[currency] = free

        return balances

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker information for a symbol."""
        endpoint = f"/ticker/t{symbol}"
        response = await self._request('GET', endpoint)

        return Ticker(
            symbol=symbol,
            bid=Decimal(str(response[0])),
            ask=Decimal(str(response[2])),
            last=Decimal(str(response[6])),
            base_volume=Decimal(str(response[7])),
            quote_volume=Decimal(str(response[7] * response[6])),  # Approximate
            timestamp=time.time()
        )

    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        """Get order book for a symbol."""
        endpoint = f"/book/t{symbol}/P0"
        params = {'len': min(limit, 100)}  # Bitfinex supports up to 100 levels

        response = await self._request('GET', endpoint, params=params)

        # Process order book data
        bids = [(Decimal(str(price)), Decimal(str(amount))) for price, count, amount in response if amount > 0]
        asks = [(Decimal(str(price)), abs(Decimal(str(amount)))) for price, count, amount in response if amount < 0]

        return OrderBook(
            bids=sorted(bids, reverse=True)[:limit],
            asks=sorted(asks)[:limit],
            timestamp=time.time()
        )

    async def create_order(self, symbol: str, order_type: str, side: str,
                         amount: Decimal, price: Optional[Decimal] = None) -> Dict[str, Any]:
        """Create a new order."""
        endpoint = "/auth/w/order/submit"

        order_data = {
            "type": order_type.upper(),
            "symbol": f"t{symbol}",
            "amount": str(amount),
            "side": side.lower(),
            "meta": {
                "aff_code": "1YqI8i9mUcR3vX7w"  # Affiliate code
            }
        }

        if order_type.lower() == 'limit':
            if price is None:
                raise ValueError("Price is required for limit orders")
            order_data['price'] = str(price)

        return await self._request('POST', endpoint, private=True, data=order_data)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of open orders."""
        endpoint = "/auth/r/orders"
        if symbol:
            endpoint = f"/auth/r/orders/t{symbol}"

        orders = await self._request('POST', endpoint, private=True)

        return [{
            'id': str(order[0]),
            'symbol': order[3].lstrip('t'),
            'amount': Decimal(str(order[6])),
            'original_amount': Decimal(str(order[7])),
            'type': order[8],
            'side': 'buy' if order[6] > 0 else 'sell',
            'price': Decimal(str(order[16])),
            'status': 'open',
            'timestamp': order[4] / 1000
        } for order in orders]

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        endpoint = "/auth/w/order/cancel"

        try:
            await self._request('POST', endpoint, private=True, data={
                'id': int(order_id)
            })
            return True
        except ExchangeError:
            return False

    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get list of available markets and their details."""
        endpoint = "/conf/pub:list:pair:exchange"
        response = await self._request('GET', endpoint)

        # Get all trading pairs
        pairs = response[0]

        # Get detailed info for each pair
        details_endpoint = "/conf/pub:info:pair"
        details_response = await self._request('GET', details_endpoint)
        details = {k: v for k, v in details_response[0].items()}

        markets = []
        for pair in pairs:
            if ':' in pair:  # Skip pairs with colons (e.g., 'tBTC:USD')
                continue

            pair_info = details.get(pair, {})

            markets.append({
                'symbol': pair,
                'base': pair[1:4],  # Extract base currency (e.g., 'BTC' from 'tBTCUSD')
                'quote': pair[4:],  # Extract quote currency (e.g., 'USD' from 'tBTCUSD')
                'precision': {
                    'price': pair_info.get('price_precision', 5),
                    'amount': pair_info.get('min_size', '0.00001').count('0') + 1
                },
                'min_amount': Decimal(str(pair_info.get('min_size', '0.00001'))),
                'min_total': Decimal(str(pair_info.get('min_size', '0.00001'))) * 1000  # Approximate
            })

        return markets