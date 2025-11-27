"""



Binance Exchange API client implementation.
"""
from typing import Any, Dict, List, Optional



class BinanceExchange(BaseExchange):
    """Binance Exchange API client."""

    BASE_URL = "https://api.binance.com/api/v3"
    WS_URL = "wss://stream.binance.com:9443/ws"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        """
        Initialize the Binance exchange client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
        """
        super().__init__(api_key, api_secret)
        self.name = "Binance"
        self._http_client = HttpClient(
            base_url=self.BASE_URL,
            api_key=api_key,
            api_secret=api_secret,
            rate_limit=1200,  # Binance has 1200 requests per minute limit
            timeout=30,
            retries=3
        )

    async def connect(self) -> None:
        """Initialize connection to Binance API."""
        await self._http_client._get_session()

    async def disconnect(self) -> None:
        """Close connection to Binance API."""
        await self._http_client.close()

    def _sign_request(self, data: Dict[str, Any]) -> str:
        """
        Sign request data with API secret.

        Args:
            data: Request parameters to sign

        Returns:
            Hex-encoded signature
        """
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(data.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def get_balance(self) -> Dict[str, Decimal]:
        """
        Get account balances.

        Returns:
            Dictionary mapping currency codes to available balance

        Raises:
            ExchangeError: If the request fails
        """
        endpoint = "/account"
        timestamp = int(time.time() * 1000)

        params = {
            'timestamp': timestamp,
            'recvWindow': 5000
        }

        # Sign the request
        params['signature'] = self._sign_request(params)

        response = await self._http_client.get(
            endpoint,
            params=params,
            auth=True
        )

        # Parse balances
        balances = {}
        for balance in response['balances']:
            free = Decimal(balance['free'])
            if free > 0:
                balances[balance['asset']] = free

        return balances

    async def get_ticker(self, symbol: str) -> Ticker:
        """
        Get ticker information for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Ticker object with market data

        Raises:
            ExchangeError: If the request fails
        """
        endpoint = "/ticker/24hr"
        response = await self._http_client.get(
            endpoint,
            params={'symbol': symbol.upper()}
        )

        return Ticker(
            symbol=symbol,
            bid=Decimal(response['bidPrice']),
            ask=Decimal(response['askPrice']),
            last=Decimal(response['lastPrice']),
            base_volume=Decimal(response['volume']),
            quote_volume=Decimal(response['quoteVolume']),
            timestamp=response['closeTime'] / 1000  # Convert to seconds
        )

    async def get_order_book(self, symbol: str, limit: int = 100) -> OrderBook:
        """
        Get order book for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Maximum number of orders to return (5, 10, 20, 50, 100, 500, 1000, 5000)

        Returns:
            OrderBook object with bids and asks

        Raises:
            ExchangeError: If the request fails
        """
        endpoint = "/depth"
        response = await self._http_client.get(
            endpoint,
            params={
                'symbol': symbol.upper(),
                'limit': min(5000, max(5, limit))  # Ensure limit is within valid range
            }
        )

        return OrderBook(
            bids=response['bids'],
            asks=response['asks'],
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
        """
        Create a new order.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            order_type: Order type ('market', 'limit', 'stop_loss', etc.)
            side: Order side ('buy' or 'sell')
            amount: Order amount in base currency
            price: Order price (required for limit orders)

        Returns:
            Order details

        Raises:
            ExchangeError: If the request fails
            ValueError: If required parameters are missing
        """
        if order_type not in ['market', 'limit']:
            raise ValueError(f"Unsupported order type: {order_type}")

        if side.lower() not in ['buy', 'sell']:
            raise ValueError(f"Invalid order side: {side}")

        if order_type == 'limit' and price is None:
            raise ValueError("Price is required for limit orders")

        endpoint = "/order"
        timestamp = int(time.time() * 1000)

        # Prepare order parameters
        params = {
            'symbol': symbol.upper(),
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': str(amount),
            'timestamp': timestamp,
            'recvWindow': 5000
        }

        # Add price for limit orders
        if order_type == 'limit':
            params['timeInForce'] = 'GTC'  # Good-Til-Canceled
            params['price'] = str(price)

        # Sign the request
        params['signature'] = self._sign_request(params)

        return await self._http_client.post(
            endpoint,
            data=params,
            auth=True
        )

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get list of open orders.

        Args:
            symbol: Optional trading pair symbol to filter orders

        Returns:
            List of open orders

        Raises:
            ExchangeError: If the request fails
        """
        endpoint = "/openOrders" if symbol else "/openOrders"
        timestamp = int(time.time() * 1000)

        params = {
            'timestamp': timestamp,
            'recvWindow': 5000
        }

        if symbol:
            params['symbol'] = symbol.upper()

        # Sign the request
        params['signature'] = self._sign_request(params)

        return await self._http_client.get(
            endpoint,
            params=params,
            auth=True
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: ID of the order to cancel
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            True if cancellation was successful, False otherwise

        Raises:
            ExchangeError: If the request fails
        """
        endpoint = "/order"
        timestamp = int(time.time() * 1000)

        params = {
            'symbol': symbol.upper(),
            'orderId': order_id,
            'timestamp': timestamp,
            'recvWindow': 5000
        }

        # Sign the request
        params['signature'] = self._sign_request(params)

        try:
            await self._http_client.delete(
                endpoint,
                params=params,
                auth=True
            )
            return True
        except Exception as e:
            # Log the error but don't raise, just return False
            self._logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_markets(self) -> List[Dict]:
        """
        Get list of available markets and their details.

        Returns:
            List of market dictionaries with trading pair information

        Raises:
            ExchangeError: If the request fails
        """
        endpoint = "/exchangeInfo"
        response = await self._http_client.get(endpoint)

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