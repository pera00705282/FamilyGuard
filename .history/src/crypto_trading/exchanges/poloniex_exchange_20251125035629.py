"""



Poloniex exchange implementation.
"""
from typing import Dict, List, Optional, Any

    BaseExchange,
    Ticker,
    OrderBook,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthenticationError
)

class PoloniexExchange(BaseExchange):
    """Poloniex exchange implementation."""

    BASE_URL = "https://api.poloniex.com"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        super().__init__(api_key, api_secret)
        self.name = "poloniex"
        self._session = None

    async def connect(self) -> None:
        """Initialize connection to Poloniex API."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def disconnect(self) -> None:
        """Close connection to Poloniex API."""
        if self._session:
            await self._session.close()
            self._session = None

    def _generate_signature(self, data: Dict[str, str]) -> str:
        """Generate signature for private API calls."""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            urlencode(data).encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, private: bool = False,
                      params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Send HTTP request to Poloniex API."""
        if params is None:
            params = {}

        url = f"{self.BASE_URL}{endpoint}"
        headers = {}

        if private:
            if not self.api_key or not self.api_secret:
                raise ExchangeAuthenticationError("API key and secret are required for private endpoints")

            params['nonce'] = int(time.time() * 1000)
            params['apiKey'] = self.api_key

            # Poloniex expects the signature in the headers
            signature = self._generate_signature(params)
            headers.update({
                'Key': self.api_key,
                'Sign': signature,
                'Content-Type': 'application/x-www-form-urlencoded'
            })

        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params if method.upper() == 'GET' else None,
                data=params if method.upper() != 'GET' else None,
                headers=headers
            ) as response:
                result = await response.json()

                if isinstance(result, dict) and 'error' in result:
                    error_msg = result.get('error', 'Unknown error')
                    if 'Invalid API key' in error_msg:
                        raise ExchangeAuthenticationError(f"Authentication failed: {error_msg}")
                    raise ExchangeError(f"API error: {error_msg}")

                return result

        except aiohttp.ClientError as e:
            raise ExchangeConnectionError(f"Connection error: {str(e)}")

    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balances."""
        endpoint = "/accounts/balances"
        response = await self._request('GET', endpoint, private=True)

        balances = {}
        for account in response:
            currency = account['currency']
            available = Decimal(account['available'])
            if available > 0:
                balances[currency] = available

        return balances

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker information for a symbol."""
        endpoint = "/markets/ticker24h"
        params = {'symbols': symbol.upper().replace('/', '_')}

        response = await self._request('GET', endpoint, params=params)
        if not response:
            raise ExchangeError(f"No ticker data for {symbol}")

        ticker_data = response[0]
        return Ticker(
            symbol=symbol,
            bid=Decimal(ticker_data['bid']),
            ask=Decimal(ticker_data['ask']),
            last=Decimal(ticker_data['close']),
            base_volume=Decimal(ticker_data['quantity']),
            quote_volume=Decimal(ticker_data['amount']),
            timestamp=time.time()
        )

    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        """Get order book for a symbol."""
        endpoint = f"/markets/{symbol.upper().replace('/', '_')}/orderBook"
        params = {'limit': min(limit, 100)}  # Poloniex supports up to 100 levels

        response = await self._request('GET', endpoint, params=params)

        return OrderBook(
            bids=[(Decimal(price), Decimal(amount)) for price, amount in response['bids']],
            asks=[(Decimal(price), Decimal(amount)) for price, amount in response['asks']],
            timestamp=time.time()
        )

    async def create_order(self, symbol: str, order_type: str, side: str,
                         amount: Decimal, price: Optional[Decimal] = None) -> Dict[str, Any]:
        """Create a new order."""
        endpoint = "/orders"

        params = {
            'symbol': symbol.upper().replace('/', '_'),
            'side': side.lower(),
            'type': order_type.lower(),
            'quantity': str(amount),
            'timeInForce': 'GTC'  # Good Till Cancelled
        }

        if order_type.lower() == 'limit':
            if price is None:
                raise ValueError("Price is required for limit orders")
            params['price'] = str(price)

        return await self._request('POST', endpoint, private=True, params=params)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of open orders."""
        endpoint = "/orders"
        params = {}

        if symbol:
            params['symbol'] = symbol.upper().replace('/', '_')

        return await self._request('GET', endpoint, private=True, params=params)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        endpoint = f"/orders/{order_id}"

        try:
            await self._request('DELETE', endpoint, private=True)
            return True
        except ExchangeError:
            return False

    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get list of available markets and their details.

        Returns:
            List[Dict[str, Any]]: List of market details including symbol, base,
                quote, precision, min_amount, and min_total
        """
        endpoint = "/markets"
        response = await self._request('GET', endpoint)

        markets = []
        for market in response:
            if market['trading']:  # Only include active markets
                markets.append({
                    'symbol': market['symbol'],
                    'base': market['baseCurrency'],
                    'quote': market['quoteCurrency'],
                    'precision': {
                        'price': market['priceScale'],
                        'amount': market['quantityScale']
                    },
                    'min_amount': Decimal(market['minQuantity']),
                    'min_total': Decimal(market['minAmount'])
                })

        return markets