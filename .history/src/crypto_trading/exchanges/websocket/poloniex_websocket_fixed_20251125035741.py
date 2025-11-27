"""



Poloniex WebSocket client implementation.
"""
from typing import Any, Dict, List, Optional, Set, Tuple


class PoloniexWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Poloniex."""

    WS_URL = "wss://ws.poloniex.com/ws"

    def __init__(self, api_key: str = None, api_secret: str = None):
        super().__init__(self.WS_URL, api_key, api_secret)
        self._subscriptions: Set[str] = set()

    async def _on_connect(self) -> None:
        """Handle connection established."""
        if self.api_key and self.api_secret:
            await self.authenticate()

        # Resubscribe to channels if reconnected
        if self._subscriptions:
            await self._resubscribe()

    async def authenticate(self) -> None:
        """Authenticate the WebSocket connection."""
        if not self.api_key or not self.api_secret:
            raise WebSocketError("API key and secret are required for authentication")

        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}GET/users/self/verify"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        auth_msg = {
            "event": "subscribe",
            "channel": ["auth"],
            "key": self.api_key,
            "signature": signature,
            "timestamp": timestamp
        }

        await self._send_json(auth_msg)

    async def subscribe(self, channel: str, **kwargs) -> None:
        """Subscribe to a channel.

        Args:
            channel: The channel to subscribe to (e.g., 'ticker', 'trades', 'book')
            **kwargs: Additional parameters for the subscription
        """
        if channel not in self._subscriptions:
            self._subscriptions.add(channel)

            if self._ws:
                msg = {
                    "event": "subscribe",
                    "channel": [channel],
                    "symbols": kwargs.get('symbols', [])
                }
                await self._send_json(msg)

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: The channel to unsubscribe from
        """
        if channel in self._subscriptions:
            self._subscriptions.remove(channel)

            if self._ws:
                msg = {
                    "event": "unsubscribe",
                    "channel": [channel]
                }
                await self._send_json(msg)

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an incoming WebSocket message."""
        if isinstance(message, list):
            # Handle data messages
            if len(message) < 2:
                return

            channel = message[0]
            data = message[1]

            if channel == 'ticker':
                await self._handle_ticker(data)
            elif channel == 'book':
                await self._handle_orderbook(data)
            elif channel == 'trades':
                await self._handle_trade(data)
            elif channel == 'auth':
                await self._handle_auth_response(data)

        elif isinstance(message, dict):
            # Handle control messages
            if message.get('event') == 'error':
                self._handle_error(f"WebSocket error: {message.get('message', 'Unknown error')}")

    async def _handle_ticker(self, data: Dict[str, Any]) -> None:
        """Handle ticker update."""
        if 'symbol' not in data:
            return

        ticker = TickerUpdate(
            symbol=data['symbol'],
            bid=Decimal(data.get('bid', '0')),
            ask=Decimal(data.get('ask', '0')),
            last=Decimal(data.get('last', '0')),
            base_volume=Decimal(data.get('baseVolume', '0')),
            quote_volume=Decimal(data.get('quoteVolume', '0')),
            timestamp=time.time()
        )

        for callback in self._callbacks['ticker']:
            await self._run_callback(callback, ticker)

    async def _handle_orderbook(self, data: Dict[str, Any]) -> None:
        """Handle order book update."""
        if 'symbol' not in data or 'bids' not in data or 'asks' not in data:
            return

        orderbook = OrderBookUpdate(
            symbol=data['symbol'],
            bids=[(Decimal(price), Decimal(amount)) for price, amount in data['bids']],
            asks=[(Decimal(price), Decimal(amount)) for price, amount in data['asks']]
        )

        for callback in self._callbacks['orderbook']:
            await self._run_callback(callback, orderbook)

    async def _handle_trade(self, data: Dict[str, Any]) -> None:
        """Handle trade update."""
        if 'symbol' not in data or 'data' not in data:
            return

        for trade_data in data['data']:
            trade = Trade(
                symbol=data['symbol'],
                price=Decimal(trade_data['price']),
                amount=Decimal(trade_data['quantity']),
                side=trade_data['takerSide'].lower(),
                timestamp=trade_data['ts'] / 1000,
                trade_id=str(trade_data['id'])
            )

            for callback in self._callbacks['trades']:
                await self._run_callback(callback, trade)

    async def _handle_account_update(self, data: Dict[str, Any]) -> None:
        """Handle account update (orders, balances)."""
        if 'data' not in data:
            return

        for callback in self._callbacks['user_data']:
            await self._run_callback(callback, data['data'])

    async def _run_callback(self, callback, *args, **kwargs):
        """Run a callback and handle any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)

    async def _handle_auth_response(self, data: Dict[str, Any]) -> None:
        """Handle authentication response."""
        if data.get('success') is not True:
            self._handle_error(f"Authentication failed: {data.get('message', 'Unknown error')}")

    async def _resubscribe(self) -> None:
        """Resubscribe to all channels after reconnection."""
        if not self._subscriptions:
            return

        msg = {
            "event": "subscribe",
            "channel": list(self._subscriptions)
        }
        await self._send_json(msg)