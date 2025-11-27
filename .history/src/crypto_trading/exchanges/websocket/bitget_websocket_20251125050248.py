"""
Bitget WebSocket client implementation.
"""
import logging
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable

from .base_websocket import BaseWebSocketClient, OrderBookUpdate, TickerUpdate, Trade, WebSocketError

logger = logging.getLogger(__name__)

class BitgetWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Bitget."""

    WS_URL = "wss://ws.bitget.com/spot/v1/stream"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        **kwargs
    ):
        """Initialize the Bitget WebSocket client.

        Args:
            api_key: Bitget API key
            api_secret: Bitget API secret
            passphrase: Bitget API passphrase
            **kwargs: Additional arguments to pass to the base class
        """
        super().__init__("wss://ws.bitget.com/spot/v1/stream", api_key, api_secret, **kwargs)
        self.passphrase = passphrase
        self._subscriptions: Set[str] = set()
        self._auth_sent = False

    def _generate_signature(self, timestamp: str) -> str:
        """Generate signature for authentication."""
        if not self.api_secret:
            raise WebSocketError("API secret is required for authentication")

        import hashlib
        import hmac

        message = f"{timestamp}GET/user/verify"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _authenticate(self) -> None:
        """Authenticate the WebSocket connection."""
        if not self.api_key or not self.api_secret or not self.passphrase:
            return

        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp)

        auth_msg = {
            "op": "login",
            "args": [{
                "apiKey": self.api_key,
                "passphrase": self.passphrase,
                "timestamp": timestamp,
                "sign": signature
            }]
        }

        await self._ws.send(json.dumps(auth_msg))
        self._auth_sent = True

    async def subscribe(self, channel: str, **kwargs) -> None:
        """Subscribe to a channel.

        Args:
            channel: Channel to subscribe to (e.g., 'ticker.BTCUSDT')
            **kwargs: Additional parameters
        """
        if not self._ws or not self._ws.open:
            raise WebSocketError("WebSocket is not connected")

        # Parse channel and symbol
        parts = channel.split('.')
        if len(parts) != 2:
            raise ValueError("Invalid channel format. Expected format: 'ticker.BTCUSDT'")

        channel_type, symbol = parts
        symbol = symbol.upper()

        # Private channels require authentication
        if channel_type in ['account', 'order', 'position'] and not self._auth_sent:
            await self._authenticate()
            # Wait a bit for authentication to complete
            await asyncio.sleep(1)

        # Build subscription string
        subscription = f"{channel_type}:{symbol}"

        if subscription in self._subscriptions:
            return

        # Send subscribe message
        msg = {
            "op": "subscribe",
            "args": [{
                "channel": channel_type,
                "instId": symbol
            }]
        }

        await self._ws.send(json.dumps(msg))
        self._subscriptions.add(subscription)

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: Channel to unsubscribe from
        """
        if not self._ws or not self._ws.open:
            return

        if channel not in self._subscriptions:
            return

        # Parse channel and symbol
        channel_type, symbol = channel.split('.')

        msg = {
            "op": "unsubscribe",
            "args": [{
                "channel": channel_type,
                "instId": symbol.upper()
            }]
        }

        await self._ws.send(json.dumps(msg))
        self._subscriptions.discard(channel)

    async def _process_ticker(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process ticker message."""
        await self._handle_ticker(symbol, data[0])

    async def _process_orderbook(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process orderbook message."""
        await self._handle_orderbook(symbol, data[0])

    async def _process_trade(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process trade message."""
        await self._handle_trades(symbol, data)

    async def _process_account(self, data: Dict[str, Any]) -> None:
        """Process account message."""
        await self._handle_account(data[0])

    async def _process_orders(self, data: Dict[str, Any]) -> None:
        """Process orders message."""
        await self._handle_orders(data[0])

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an incoming WebSocket message."""
        if 'event' in message:
            if message['event'] == 'error':
                logger.error("WebSocket error: %s", message.get('message'))
            elif message['event'] == 'subscribe' and message.get('code') != 0:
                logger.error("Subscription error: %s", message.get('msg'))
            return

        if 'arg' not in message or 'data' not in message:
            return

        channel = message['arg'].get('channel')
        symbol = message['arg'].get('instId')
        data = message['data']

        if not channel or not symbol or not data:
            return

        processor = getattr(self, f"_process_{channel}", None)
        if processor:
            await processor(symbol, data)
        else:
            logger.warning("No processor for channel: %s", channel)

    async def _handle_ticker(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle ticker update."""
        import time
        from decimal import Decimal

        ticker = TickerUpdate(
            symbol=symbol,
            bid=Decimal(str(data.get('bestBid', 0))),
            ask=Decimal(str(data.get('bestAsk', 0))),
            last=Decimal(str(data.get('last', 0))),
            base_volume=Decimal(str(data.get('baseVolume', 0))),
            quote_volume=Decimal(str(data.get('quoteVolume', 0))),
            timestamp=int(data.get('ts', time.time() * 1000)) / 1000
        )

        for callback in self._callbacks['ticker']:
            await self._run_callback(callback, ticker)

    async def _handle_orderbook(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle order book update."""
        import time
        from decimal import Decimal

        bids = [(Decimal(str(price)), Decimal(str(amount))) 
                for price, amount in data.get('bids', [])]
        asks = [(Decimal(str(price)), Decimal(str(amount))) 
                for price, amount in data.get('asks', [])]

        orderbook = OrderBookUpdate(
            symbol=symbol,
            bids=sorted(bids, reverse=True),
            asks=sorted(asks),
            timestamp=data.get('ts', int(time.time() * 1000)) / 1000
        )

        for callback in self._callbacks['orderbook']:
            await self._run_callback(callback, orderbook)

    async def _handle_trades(self, symbol: str, trades_data: List[Dict[str, Any]]) -> None:
        """Handle trade updates."""
        import time
        from decimal import Decimal

        for trade_data in trades_data:
            trade = Trade(
                symbol=symbol,
                price=Decimal(str(trade_data.get('price', 0))),
                amount=Decimal(str(trade_data.get('size', 0))),
                side=trade_data.get('side', '').lower(),
                timestamp=int(trade_data.get('ts', time.time() * 1000)) / 1000,
                trade_id=str(trade_data.get('tradeId', ''))
            )

            for callback in self._callbacks['trades']:
                await self._run_callback(callback, trade)

    async def _handle_account(self, data: Dict[str, Any]) -> None:
        """Handle account updates."""
        for callback in self._callbacks['user_data']:
            await self._run_callback(callback, {
                'type': 'account',
                'data': data
            })

    async def _handle_orders(self, data: Dict[str, Any]) -> None:
        """Handle order updates."""
        for callback in self._callbacks['user_data']:
            await self._run_callback(callback, {
                'type': 'order',
                'data': data
            })

    async def _run_callback(self, callback: Callable[..., Awaitable[None]], *args, **kwargs):
        """Run a callback and handle any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)