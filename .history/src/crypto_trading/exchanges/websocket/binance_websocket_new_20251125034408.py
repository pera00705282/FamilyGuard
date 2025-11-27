"""



Binance WebSocket client implementation with support for multiple trading pairs.
"""
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable



# Configure logger
logger = logging.getLogger(__name__)

class BinanceWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Binance with support for multiple trading pairs."""

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
            api_key: Binance API key (required for user data streams)
            api_secret: Binance API secret (required for user data streams)
            **kwargs: Additional arguments for BaseWebSocketClient
        """
        url = kwargs.pop('url', self.WS_URL)
        super().__init__(url, api_key, api_secret, **kwargs)
        self._listen_key = None
        self._user_data_task = None
        self._combined = False
        self._subscriptions = set()

    async def subscribe(self, channels: Union[str, List[str]], **kwargs) -> None:
        """Subscribe to one or more channels.

        Args:
            channels: Channel or list of channels to subscribe to
                     (e.g., 'btcusdt@ticker' or ['btcusdt@ticker', 'ethusdt@ticker'])
            **kwargs: Additional parameters

        Raises:
            WebSocketConnectionError: If WebSocket is not connected
            ValueError: If channel format is invalid
        """
        if not self._ws or not self._ws.open:
            raise WebSocketConnectionError("WebSocket is not connected")

        # Handle user data subscription
        if channels == 'user_data' and self.api_key and self.api_secret:
            await self._subscribe_user_data()
            return

        # Convert single channel to list for uniform processing
        if isinstance(channels, str):
            channels = [channels]

        new_streams = []
        for channel in channels:
            if '@' not in channel:
                raise ValueError(f"Invalid channel format: {channel}. Expected format: 'symbol@stream'")

            symbol, stream_type = channel.split('@', 1)
            stream = f"{symbol.lower()}@{stream_type}"

            if stream not in self._subscriptions:
                self._subscriptions.add(stream)
                new_streams.append(stream)

        if not new_streams:
            return  # No new streams to subscribe to

        # If we have multiple subscriptions, use combined streams
        if len(self._subscriptions) > 1 or any(s in new_streams[0] for s in ['depth', 'aggTrade', 'trade']):
            await self._subscribe_combined()
        else:
            # For single stream, use standard URL
            if self._combined:
                await self._unsubscribe_all()
                self._combined = False
                self.url = self.WS_URL
                await self._connect()

            # Subscribe to the new stream
            payload = {
                "method": "SUBSCRIBE",
                "params": new_streams,
                "id": int(time.time() * 1000)
            }
            await self._ws.send(json.dumps(payload))

    async def _subscribe_combined(self) -> None:
        """Subscribe to all streams using combined streams URL."""
        if not self._subscriptions:
            return

        # If already using combined streams, just update the subscription
        if self._combined:
            await self._unsubscribe_all()
        else:
            # Switch to combined streams
            await self.disconnect()
            self._combined = True
            self.url = self.WS_URL_COMBINED.format('/'.join(self._subscriptions))
            await self._connect()

    async def _unsubscribe_all(self) -> None:
        """Unsubscribe from all streams."""
        if not self._ws or not self._ws.open:
            return

        if self._combined:
            await self.disconnect()
            self._combined = False
            self.url = self.WS_URL
            await self._connect()
        else:
            payload = {
                "method": "UNSUBSCRIBE",
                "params": list(self._subscriptions),
                "id": int(time.time() * 1000)
            }
            await self._ws.send(json.dumps(payload))

        self._subscriptions.clear()

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Args:
            message: Raw WebSocket message
        """
        try:
            data = json.loads(message)

            # Handle combined stream format
            if 'stream' in data and 'data' in data:
                stream = data['stream']
                if '@' not in stream:
                    logger.warning(f"Invalid stream format: {stream}")
                    return

                symbol = stream.split('@')[0].lower()
                stream_data = data['data']

                # Route to appropriate handler based on stream type
                if 'depth' in stream:
                    await self._handle_orderbook(symbol, stream_data)
                elif 'ticker' in stream or 'bookTicker' in stream:
                    await self._handle_ticker(symbol, stream_data)
                elif 'trade' in stream or 'aggTrade' in stream:
                    await self._handle_trade(symbol, stream_data)
                elif 'kline' in stream:
                    await self._handle_kline(symbol, stream_data)
                else:
                    logger.debug(f"Unhandled stream type: {stream}")

            # Handle standard event format
            elif 'e' in data:
                event_type = data['e']
                symbol = data.get('s', '').lower()

                if event_type == 'depthUpdate':
                    await self._handle_orderbook(symbol, data)
                elif event_type in ['24hrTicker', 'bookTicker']:
                    await self._handle_ticker(symbol, data)
                elif event_type in ['trade', 'aggTrade']:
                    await self._handle_trade(symbol, data)
                elif event_type == 'kline':
                    await self._handle_kline(symbol, data)
                elif event_type == 'executionReport':
                    await self._handle_execution_report(data)
                elif event_type == 'outboundAccountPosition':
                    await self._handle_balance_update(data)
                else:
                    logger.debug(f"Unhandled event type: {event_type}")

            # Handle subscription confirmation
            elif 'result' in data and data.get('result') is None and 'id' in data:
                logger.debug(f"Subscription confirmed: {data}")

            # Handle error messages
            elif 'error' in data:
                logger.error(f"WebSocket error: {data['error']}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)

    async def _handle_ticker(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle ticker update."""
        try:
            ticker = TickerUpdate(
                symbol=symbol.upper(),
                bid=Decimal(data.get('b', data.get('bestBidPrice', '0'))),
                ask=Decimal(data.get('a', data.get('bestAskPrice', '0'))),
                last=Decimal(data.get('c', data.get('lastPrice', '0'))),
                base_volume=Decimal(data.get('v', data.get('volume', '0'))),
                quote_volume=Decimal(data.get('q', data.get('quoteVolume', '0'))),
                timestamp=data.get('E', data.get('time', 0)) / 1000
            )

            for callback in self._callbacks.get('ticker', []):
                await self._run_callback(callback, ticker)

        except (KeyError, ValueError) as e:
            logger.error(f"Error processing ticker update: {e}", exc_info=True)

    async def _handle_orderbook(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle order book update."""
        try:
            def to_decimal(d):
                return [(Decimal(price), Decimal(amount)) for price, amount in d]

            orderbook = OrderBookUpdate(
                symbol=symbol.upper(),
                bids=to_decimal(data.get('b', data.get('bids', []))),
                asks=to_decimal(data.get('a', data.get('asks', []))),
                timestamp=data.get('E', data.get('lastUpdateId', 0)) / 1000
            )

            for callback in self._callbacks.get('orderbook', []):
                await self._run_callback(callback, orderbook)

        except (KeyError, ValueError) as e:
            logger.error(f"Error processing order book update: {e}", exc_info=True)

    async def _handle_trade(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle trade update."""
        try:
            trade = Trade(
                symbol=symbol.upper(),
                price=Decimal(data['p']),
                amount=Decimal(data['q']),
                side='buy' if data.get('m', data.get('isBuyerMaker', False)) else 'sell',
                timestamp=data.get('T', data.get('E', 0)) / 1000,
                trade_id=str(data.get('t', data.get('a', '')))
            )

            for callback in self._callbacks.get('trades', []):
                await self._run_callback(callback, trade)

        except (KeyError, ValueError) as e:
            logger.error(f"Error processing trade update: {e}", exc_info=True)

    async def _handle_kline(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle kline/candlestick update."""
        try:
            kline = data.get('k', {})
            kline_data = {
                'symbol': symbol.upper(),
                'open': Decimal(kline.get('o', '0')),
                'high': Decimal(kline.get('h', '0')),
                'low': Decimal(kline.get('l', '0')),
                'close': Decimal(kline.get('c', '0')),
                'volume': Decimal(kline.get('v', '0')),
                'timestamp': kline.get('t', 0) / 1000,
                'is_closed': kline.get('x', False)
            }

            for callback in self._callbacks.get('kline', []):
                await self._run_callback(callback, kline_data)

        except (KeyError, ValueError) as e:
            logger.error(f"Error processing kline update: {e}", exc_info=True)

    async def _handle_execution_report(self, data: Dict[str, Any]) -> None:
        """Handle execution report (order update)."""
        try:
            order_update = {
                'symbol': data['s'],
                'client_order_id': data.get('c'),
                'order_id': str(data.get('i')),
                'side': data.get('S').lower(),
                'order_type': data.get('o').lower(),
                'status': data.get('X').lower(),
                'price': Decimal(data.get('p', '0')),
                'quantity': Decimal(data.get('q', '0')),
                'executed_quantity': Decimal(data.get('z', '0')),
                'timestamp': data.get('E', 0) / 1000
            }

            for callback in self._callbacks.get('order_update', []):
                await self._run_callback(callback, order_update)

        except (KeyError, ValueError) as e:
            logger.error(f"Error processing execution report: {e}", exc_info=True)

    async def _handle_balance_update(self, data: Dict[str, Any]) -> None:
        """Handle balance update."""
        try:
            balances = {}
            for balance in data.get('B', []):
                asset = balance['a']
                free = Decimal(balance.get('f', '0'))
                locked = Decimal(balance.get('l', '0'))
                balances[asset] = {
                    'free': free,
                    'locked': locked,
                    'total': free + locked
                }

            balance_update = {
                'event_time': data.get('E', 0) / 1000,
                'balances': balances
            }

            for callback in self._callbacks.get('balance', []):
                await self._run_callback(callback, balance_update)

        except (KeyError, ValueError) as e:
            logger.error(f"Error processing balance update: {e}", exc_info=True)

    async def _run_callback(self, callback: Callable[..., Awaitable[None]], *args, **kwargs) -> None:
        """Run a callback and handle any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                # Run synchronous callbacks in a thread
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, callback, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)

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
            user_data_url = f"{self.WS_URL}/{self._listen_key}"
            await self.disconnect()
            self.url = user_data_url
            await self._connect()

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
            try:
                async with aiohttp.ClientSession() as session:
                    await session.delete(
                        f'https://api.binance.com/api/v3/userDataStream?listenKey={self._listen_key}',
                        headers={"X-MBX-APIKEY": self.api_key}
                    )
            except Exception as e:
                logger.error(f"Error closing user data stream: {e}")

            self._listen_key = None

        await super().disconnect()
        self._combined = False
        self._subscriptions.clear()