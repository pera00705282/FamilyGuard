"""



Bybit WebSocket client implementation.
"""
from typing import Any, Dict, List, Optional, Set, Tuple


class BybitWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Bybit."""

    WS_URL = "wss://stream.bybit.com/realtime"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs
    ):
        """Initialize the Bybit WebSocket client.

        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            **kwargs: Additional arguments for BaseWebSocketClient
        """
        super().__init__(self.WS_URL, api_key, api_secret, **kwargs)
        self._subscriptions: Set[str] = set()
        self._auth_sent = False

    async def _authenticate(self) -> None:
        """Authenticate the WebSocket connection."""
        if not self.api_key or not self.api_secret:
            return

        expires = int((time.time() + 5) * 1000)  # 5 seconds from now
        signature = self._generate_signature(f"GET/realtime{expires}")

        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }

        await self._ws.send(json.dumps(auth_msg))
        self._auth_sent = True

    def _generate_signature(self, message: str) -> str:
        """Generate signature for authentication."""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

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
        if channel_type in ['position', 'execution', 'order', 'stop_order'] and not self._auth_sent:
            await self._authenticate()
            # Wait a bit for authentication to complete
            await asyncio.sleep(1)

        # Build subscription string
        subscription = f"{channel_type}.{symbol}"

        if subscription in self._subscriptions:
            return

        # Send subscribe message
        msg = {
            "op": "subscribe",
            "args": [subscription]
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

        msg = {
            "op": "unsubscribe",
            "args": [channel]
        }

        await self._ws.send(json.dumps(msg))
        self._subscriptions.discard(channel)

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an incoming WebSocket message."""
        if 'topic' not in message:
            # Handle control messages
            if 'success' in message:
                if message.get('request', {}).get('op') == 'auth':
                    if message['success']:
                        logger.info("Successfully authenticated with Bybit WebSocket")
                    else:
                        logger.error(f"Authentication failed: {message.get('ret_msg')}")
                elif message.get('request', {}).get('op') in ['subscribe', 'unsubscribe']:
                    if not message['success']:
                        logger.error(f"Subscription error: {message.get('ret_msg')}")
            return

        topic = message['topic']
        data = message.get('data', {})

        if 'tickers' in topic:
            await self._handle_ticker(topic, data)
        elif 'orderBookL2_25' in topic or 'orderBook_200' in topic:
            await self._handle_orderbook(topic, data, message.get('type'))
        elif 'trade' in topic:
            await self._handle_trade(topic, data)
        elif 'position' in topic:
            await self._handle_position(data)
        elif 'execution' in topic:
            await self._handle_execution(data)
        elif 'order' in topic:
            await self._handle_order(data)

    async def _handle_ticker(self, topic: str, data: Dict[str, Any]) -> None:
        """Handle ticker update."""
        if not data or not isinstance(data, list):
            return

        symbol = topic.split('.')[-1]
        ticker_data = data[0] if isinstance(data, list) else data

        ticker = TickerUpdate(
            symbol=symbol,
            bid=Decimal(ticker_data.get('bid_price', 0)),
            ask=Decimal(ticker_data.get('ask_price', 0)),
            last=Decimal(ticker_data.get('last_price', 0)),
            base_volume=Decimal(ticker_data.get('volume_24h', 0)),
            quote_volume=Decimal(ticker_data.get('turnover_24h', 0)),
            timestamp=ticker_data.get('timestamp', time.time() * 1000) / 1000
        )

        for callback in self._callbacks['ticker']:
            await self._run_callback(callback, ticker)

    async def _handle_orderbook(self, topic: str, data: Dict[str, Any], update_type: str = None) -> None:
        """Handle order book update."""
        symbol = topic.split('.')[-1]

        if update_type == 'snapshot':
            # Full order book snapshot
            bids = [(Decimal(item['price']), Decimal(item['size']))
                   for item in data if item['side'] == 'Buy']
            asks = [(Decimal(item['price']), Decimal(item['size']))
                   for item in data if item['side'] == 'Sell']
        else:
            # Delta update
            bids = []
            asks = []

            for item in data.get('delete', []):
                if item['side'] == 'Buy':
                    bids.append((Decimal(item['price']), Decimal(0)))
                else:
                    asks.append((Decimal(item['price']), Decimal(0)))

            for item in data.get('update', []):
                if item['side'] == 'Buy':
                    bids.append((Decimal(item['price']), Decimal(item['size'])))
                else:
                    asks.append((Decimal(item['price']), Decimal(item['size'])))

            for item in data.get('insert', []):
                if item['side'] == 'Buy':
                    bids.append((Decimal(item['price']), Decimal(item['size'])))
                else:
                    asks.append((Decimal(item['price']), Decimal(item['size'])))

        orderbook = OrderBookUpdate(
            symbol=symbol,
            bids=sorted(bids, reverse=True),
            asks=sorted(asks),
            timestamp=time.time()
        )

        for callback in self._callbacks['orderbook']:
            await self._run_callback(callback, orderbook)

    async def _handle_trade(self, topic: str, data: Dict[str, Any]) -> None:
        """Handle trade update."""
        if not data or not isinstance(data, list):
            return

        symbol = topic.split('.')[-1]

        for trade_data in data:
            trade = Trade(
                symbol=symbol,
                price=Decimal(trade_data.get('price', 0)),
                amount=Decimal(trade_data.get('size', 0)),
                side=trade_data.get('side', '').lower(),
                timestamp=trade_data.get('timestamp', time.time() * 1000) / 1000,
                trade_id=str(trade_data.get('trade_id', ''))
            )

            for callback in self._callbacks['trades']:
                await self._run_callback(callback, trade)

    async def _handle_position(self, data: Dict[str, Any]) -> None:
        """Handle position update."""
        for callback in self._callbacks['user_data']:
            await self._run_callback(callback, {
                'type': 'position',
                'data': data
            })

    async def _handle_execution(self, data: Dict[str, Any]) -> None:
        """Handle execution update."""
        for callback in self._callbacks['user_data']:
            await self._run_callback(callback, {
                'type': 'execution',
                'data': data
            })

    async def _handle_order(self, data: Dict[str, Any]) -> None:
        """Handle order update."""
        for callback in self._callbacks['user_data']:
            await self._run_callback(callback, {
                'type': 'order',
                'data': data
            })

    async def _run_callback(self, callback, *args, **kwargs):
        """Run a callback and handle any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)