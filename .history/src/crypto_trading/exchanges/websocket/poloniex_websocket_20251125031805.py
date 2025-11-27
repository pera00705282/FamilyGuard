


""
Poloniex WebSocket client implementation.
"""
import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from decimal import Decimal
import aiohttp
import websockets
from websockets.client import WebSocketClientProtocol

from .base_websocket import BaseWebSocketClient, OrderBookUpdate, TickerUpdate, Trade, WebSocketError

class PoloniexWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Poloniex."""

    WS_URL = "wss://ws.poloniex.com/ws"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs
    ):
        """Initialize the Poloniex WebSocket client.

        Args:
            api_key: Poloniex API key
            api_secret: Poloniex API secret
            **kwargs: Additional arguments for BaseWebSocketClient
        """
        super().__init__(self.WS_URL, api_key, api_secret, **kwargs)
        self._channels: Dict[str, Set[str]] = {
            'ticker': set(),
            'book': set(),
            'trades': set(),
            'orders': set(),
            'balances': set()
        }

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate signature for private API calls."""
        if not self.api_secret:
            raise WebSocketError("API secret is required for private channels")

        return hmac.new(
            self.api_secret.encode('utf-8'),
            json.dumps(data).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _authenticate(self) -> None:
        """Authenticate the WebSocket connection."""
        if not self.api_key or not self.api_secret:
            return

        timestamp = str(int(time.time() * 1000))
        signature_data = {
            'key': self.api_key,
            'signatureTimestamp': timestamp
        }

        signature = self._generate_signature(signature_data)

        auth_msg = {
            'event': 'subscribe',
            'channel': ['auth'],
            'data': {
                'key': self.api_key,
                'signature': signature,
                'signatureTimestamp': timestamp
            }
        }

        await self._ws.send(json.dumps(auth_msg))

    async def subscribe(self, channel: str, **kwargs) -> None:
        """Subscribe to a channel.

        Args:
            channel: Channel to subscribe to (e.g., 'ticker.BTC_USDT')
            **kwargs: Additional parameters
        """
        if not self._ws or not self._ws.open:
            raise WebSocketError("WebSocket is not connected")

        # Parse channel and symbol
        parts = channel.split('.')
        if len(parts) != 2:
            raise ValueError("Invalid channel format. Expected format: 'ticker.BTC_USDT'")

        channel_type, symbol = parts
        symbol = symbol.upper().replace('/', '_')

        # Track subscriptions
        if channel_type in self._channels and symbol not in self._channels[channel_type]:
            self._channels[channel_type].add(symbol)

        # Build subscribe message
        msg = {
            'event': 'subscribe',
            'channel': [channel_type],
            'symbols': [symbol]
        }

        if channel_type in ['orders', 'balances']:
            await self._authenticate()

        await self._ws.send(json.dumps(msg))

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: Channel to unsubscribe from
        """
        if not self._ws or not self._ws.open:
            return

        parts = channel.split('.')
        if len(parts) != 2:
            return

        channel_type, symbol = parts
        symbol = symbol.upper().replace('/', '_')

        if channel_type in self._channels and symbol in self._channels[channel_type]:
            self._channels[channel_type].remove(symbol)

            msg = {
                'event': 'unsubscribe',
                'channel': [channel_type],
                'symbols': [symbol]
            }

            await self._ws.send(json.dumps(msg))

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an incoming WebSocket message."""
        if isinstance(message, list):
            # Handle data messages
            if len(message) < 2:
                return

            channel_id = message[0]
            data = message[1]

            if channel_id == 1002:  # Ticker data
                await self._handle_ticker(data)
            elif channel_id == 100:  # Order book updates
                await self._handle_orderbook(data)
            elif channel_id == 101:  # Trades
                await self._handle_trade(data)
            elif channel_id == 1000:  # Account notifications
                await self._handle_account_update(data)

        elif isinstance(message, dict):
            # Handle control messages
            if message.get('event') == 'info':
                logger.info(f"WebSocket info: {message.get('message')}")
            elif message.get('event') == 'subscribed':
                logger.info(f"Subscribed to {message.get('channel')}")
            elif message.get('event') == 'error':
                logger.error(f"WebSocket error: {message.get('message')}")

    async def _handle_ticker(self, data: Dict[str, Any]) -> None:
        """Handle ticker update."""
        if 'symbol' not in data:
            return

        ticker = TickerUpdate(
            symbol=data['symbol'],
            bid=Decimal(data['bid']),
            ask=Decimal(data['ask']),
            last=Decimal(data['last']),
            base_volume=Decimal(data['baseVolume']),
            quote_volume=Decimal(data['quoteVolume']),
            timestamp=data['ts'] / 1000
        )

        for callback in self._callbacks['ticker']:
            await self._run_callback(callback, ticker)

    async def _handle_orderbook(self, data: Dict[str, Any]) -> None:
        """Handle order book update."""
        if 'symbol' not in data:
            return

        orderbook = OrderBookUpdate(
            symbol=data['symbol'],
            bids=[(Decimal(price), Decimal(amount)) for price, amount in data.get('bids', [])],
            asks=[(Decimal(price), Decimal(amount)) for price, amount in data.get('asks', [])],
            timestamp=data['ts'] / 1000
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