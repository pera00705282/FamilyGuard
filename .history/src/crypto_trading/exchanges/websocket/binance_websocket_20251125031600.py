


""
Binance WebSocket client implementation.
"""
import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from .base_websocket import BaseWebSocketClient, OrderBookUpdate, TickerUpdate, Trade

class BinanceWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Binance."""

    WS_URL = "wss://stream.binance.com:9443/ws"
    WS_URL_COMBINED = "wss://stream.binance.com:9443/stream?streams={}"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs
    ):
        """Initialize the Binance WebSocket client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            **kwargs: Additional arguments for BaseWebSocketClient
        """
        url = kwargs.pop('url', self.WS_URL)
        super().__init__(url, api_key, api_secret, **kwargs)
        self._listen_key = None
        self._user_data_task = None

    async def subscribe(self, channel: str, **kwargs) -> None:
        """Subscribe to a channel.

        Args:
            channel: Channel to subscribe to (e.g., 'btcusdt@ticker')
            **kwargs: Additional parameters
        """
        if not self._ws or not self._ws.open:
            raise WebSocketConnectionError("WebSocket is not connected")

        if channel == 'user_data' and self.api_key and self.api_secret:
            await self._subscribe_user_data()
            return

        # For public channels
        if '@' not in channel:
            raise ValueError("Invalid channel format. Expected format: 'symbol@channel'")

        symbol, channel_type = channel.split('@', 1)
        stream = f"{symbol.lower()}@{channel_type}"

        if stream in self._subscriptions:
            return

        if len(self._subscriptions) >= 1024:
            raise ValueError("Maximum number of subscriptions (1024) reached")

        # If using combined streams URL, we need to resubscribe to all streams
        if hasattr(self, '_combined') and self._combined:
            await self._resubscribe_combined(stream, subscribe=True)
        else:
            # For single stream connection
            await self._ws.send(json.dumps({
                "method": "SUBSCRIBE",
                "params": [stream],
                "id": int(time.time() * 1000)
            }))

        self._subscriptions.add(stream)

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: Channel to unsubscribe from
        """
        if not self._ws or not self._ws.open:
            return

        if channel == 'user_data' and self._listen_key:
            await self._unsubscribe_user_data()
            return

        if '@' not in channel:
            return

        symbol, channel_type = channel.split('@', 1)
        stream = f"{symbol.lower()}@{channel_type}"

        if stream not in self._subscriptions:
            return

        if hasattr(self, '_combined') and self._combined:
            await self._resubscribe_combined(stream, subscribe=False)
        else:
            await self._ws.send(json.dumps({
                "method": "UNSUBSCRIBE",
                "params": [stream],
                "id": int(time.time() * 1000)
            }))

        self._subscriptions.discard(stream)

    async def _subscribe_user_data(self) -> None:
        """Subscribe to user data stream."""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret are required for user data")

        # Create a new session for the listen key request
        async with aiohttp.ClientSession() as session:
            # Get a listen key
            async with session.post(
                'https://api.binance.com/api/v3/userDataStream',
                headers={"X-MBX-APIKEY": self.api_key}
            ) as response:
                data = await response.json()
                self._listen_key = data['listenKey']

            # Start the keep-alive task
            self._user_data_task = asyncio.create_task(self._keep_alive_listen_key())

            # Connect to the user data stream
            user_data_url = f"wss://stream.binance.com:9443/ws/{self._listen_key}"
            await self._ws.close()
            self._ws = await websockets.connect(user_data_url)

            # Restart the consumer task
            if self._consumer_task:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

            self._consumer_task = asyncio.create_task(self._consumer())

    async def _unsubscribe_user_data(self) -> None:
        """Unsubscribe from user data stream."""
        if not self._listen_key:
            return

        # Cancel the keep-alive task
        if self._user_data_task:
            self._user_data_task.cancel()
            try:
                await self._user_data_task
            except asyncio.CancelledError:
                pass
            self._user_data_task = None

        # Close the user data stream
        async with aiohttp.ClientSession() as session:
            await session.delete(
                f'https://api.binance.com/api/v3/userDataStream?listenKey={self._listen_key}',
                headers={"X-MBX-APIKEY": self.api_key}
            )

        self._listen_key = None

    async def _keep_alive_listen_key(self) -> None:
        """Keep the user data stream alive."""
        while True:
            try:
                await asyncio.sleep(30 * 60)  # 30 minutes
                async with aiohttp.ClientSession() as session:
                    await session.put(
                        f'https://api.binance.com/api/v3/userDataStream?listenKey={self._listen_key}',
                        headers={"X-MBX-APIKEY": self.api_key}
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error keeping listen key alive: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an incoming WebSocket message."""
        # Handle user data stream
        if 'e' in message and message['e'] == 'outboundAccountPosition':
            # Balance update
            for balance in message['B']:
                for callback in self._callbacks['user_data']:
                    await self._run_callback(callback, {
                        'event': 'balance',
                        'asset': balance['a'],
                        'free': Decimal(balance['f']),
                        'locked': Decimal(balance['l'])
                    })

        elif 'e' in message and message['e'] == 'executionReport':
            # Order update
            order_update = {
                'event': 'order_update',
                'symbol': message['s'],
                'side': message['S'].lower(),
                'order_type': message['o'].lower(),
                'quantity': Decimal(message['q']),
                'price': Decimal(message['p']) if 'p' in message else None,
                'status': message['X'].lower(),
                'order_id': str(message['i']),
                'client_order_id': message['c'],
                'executed_quantity': Decimal(message['z']),
                'timestamp': message['E'] / 1000
            }

            for callback in self._callbacks['user_data']:
                await self._run_callback(callback, order_update)

        # Handle market data
        elif 'stream' in message:
            # Combined stream message
            stream = message['stream']
            data = message['data']

            if '@ticker' in stream:
                await self._handle_ticker(stream.split('@')[0], data)
            elif '@depth' in stream:
                await self._handle_orderbook(stream.split('@')[0], data)
            elif '@trade' in stream:
                await self._handle_trade(stream.split('@')[0], data)

        elif 'e' in message:
            # Single stream message
            if message['e'] == '24hrTicker':
                await self._handle_ticker(message['s'].lower(), message)
            elif message['e'] == 'depthUpdate':
                await self._handle_orderbook(message['s'].lower(), message)
            elif message['e'] == 'trade':
                await self._handle_trade(message['s'].lower(), message)

    async def _handle_ticker(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle ticker update."""
        ticker = TickerUpdate(
            symbol=symbol.upper(),
            bid=Decimal(data['b']),
            ask=Decimal(data['a']),
            last=Decimal(data['c']),
            base_volume=Decimal(data['v']),
            quote_volume=Decimal(data['q']),
            timestamp=data['E'] / 1000
        )

        for callback in self._callbacks['ticker']:
            await self._run_callback(callback, ticker)

    async def _handle_orderbook(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle order book update."""
        # Convert price/quantity strings to Decimal


        def to_decimal(d):
            return [(Decimal(price), Decimal(amount)) for price, amount in d]

        orderbook = OrderBookUpdate(
            symbol=symbol.upper(),
            bids=to_decimal(data.get('b', [])),
            asks=to_decimal(data.get('a', [])),
            timestamp=data['E'] / 1000
        )

        for callback in self._callbacks['orderbook']:
            await self._run_callback(callback, orderbook)

    async def _handle_trade(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle trade update."""
        trade = Trade(
            symbol=symbol.upper(),
            price=Decimal(data['p']),
            amount=Decimal(data['q']),
            side='buy' if data['m'] else 'sell',
            timestamp=data['T'] / 1000,
            trade_id=str(data['t'])
        )

        for callback in self._callbacks['trades']:
            await self._run_callback(callback, trade)

    async def _run_callback(self, callback, *args, **kwargs):
        """Run a callback and handle any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)

    async def _resubscribe_combined(self, stream: str, subscribe: bool = True) -> None:
        """Resubscribe to all streams when using combined streams."""
        # Close the current connection
        await self.disconnect()

        # Update subscriptions
        if subscribe:
            self._subscriptions.add(stream)
        else:
            self._subscriptions.discard(stream)

        if not self._subscriptions:
            return

        # Reconnect with updated streams
        streams = '/'.join(self._subscriptions)
        self.url = self.WS_URL_COMBINED.format(streams)
        self._combined = True

        await self._connect()

    async def connect(self) -> None:
        """Connect to the WebSocket server."""
        # If we have multiple subscriptions, use the combined streams URL
        if len(self._subscriptions) > 1:
            streams = '/'.join(self._subscriptions)
            self.url = self.WS_URL_COMBINED.format(streams)
            self._combined = True
        else:
            self._combined = False

        await super().connect()

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        if self._user_data_task:
            self._user_data_task.cancel()
            try:
                await self._user_data_task
            except asyncio.CancelledError:
                pass
            self._user_data_task = None

        if self._listen_key:
            await self._unsubscribe_user_data()

        await super().disconnect()