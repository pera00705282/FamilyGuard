"""



Base WebSocket client for real-time market data streaming.
"""
from typing import Any, Callable, Dict, List, Optional, Set, Union


class WebSocketError(Exception):
    """Base exception for WebSocket related errors."""
    pass


class WebSocketDisconnectedError(WebSocketError):
    """Raised when the WebSocket connection is lost."""
    pass


class OrderBookUpdate:
    """Represents an order book update."""

    def __init__(self, symbol: str, bids: List[tuple], asks: List[tuple], timestamp: float):
        """
        Initialize order book update.

        Args:
            symbol: Trading pair symbol
            bids: List of bid tuples (price, amount)
            asks: List of ask tuples (price, amount)
            timestamp: Unix timestamp of the update
        """
        self.symbol = symbol
        self.bids = sorted(((Decimal(str(price)), Decimal(str(amount)))
                          for price, amount in bids), reverse=True)
        self.asks = sorted(((Decimal(str(price)), Decimal(str(amount)))
                          for price, amount in asks))
        self.timestamp = timestamp


class TickerUpdate:
    """Represents a ticker update."""

    def __init__(self, symbol: str, bid: Union[float, Decimal, str],
                 ask: Union[float, Decimal, str], last: Union[float, Decimal, str],
                 base_volume: Union[float, Decimal, str],
                 quote_volume: Union[float, Decimal, str], timestamp: float):
        """
        Initialize ticker update.

        Args:
            symbol: Trading pair symbol
            bid: Current best bid price
            ask: Current best ask price
            last: Last traded price
            base_volume: 24h trading volume in base currency
            quote_volume: 24h trading volume in quote currency
            timestamp: Unix timestamp of the update
        """
        self.symbol = symbol
        self.bid = Decimal(str(bid))
        self.ask = Decimal(str(ask))
        self.last = Decimal(str(last))
        self.base_volume = Decimal(str(base_volume))
        self.quote_volume = Decimal(str(quote_volume))
        self.timestamp = timestamp


class Trade:
    """Represents a trade."""

    def __init__(self, symbol: str, price: Union[float, Decimal, str],
                 amount: Union[float, Decimal, str], side: str,
                 timestamp: float, trade_id: str = ""):
        """
        Initialize trade.

        Args:
            symbol: Trading pair symbol
            price: Trade price
            amount: Trade amount
            side: Trade side ('buy' or 'sell')
            timestamp: Unix timestamp of the trade
            trade_id: Unique trade identifier
        """
        self.symbol = symbol
        self.price = Decimal(str(price))
        self.amount = Decimal(str(amount))
        self.side = side.lower()
        self.timestamp = timestamp
        self.trade_id = trade_id


class BaseWebSocketClient(ABC):
    """Base WebSocket client for real-time market data."""

    def __init__(self, ws_url: str, api_key: str = "", api_secret: str = ""):
        """
        Initialize the WebSocket client.

        Args:
            ws_url: WebSocket URL
            api_key: API key for private channels
            api_secret: API secret for private channels
        """
        self.ws_url = ws_url
        self.api_key = api_key
        self.api_secret = api_secret
        self._ws = None
        self._running = False
        self._callbacks = {
            'ticker': [],
            'orderbook': [],
            'trades': [],
            'user_data': []
        }
        self._subscriptions: Set[str] = set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def on_ticker(self, callback: Callable[[TickerUpdate], None]) -> None:
        """Register a callback for ticker updates."""
        self._callbacks['ticker'].append(callback)

    def on_orderbook(self, callback: Callable[[OrderBookUpdate], None]) -> None:
        """Register a callback for order book updates."""
        self._callbacks['orderbook'].append(callback)

    def on_trades(self, callback: Callable[[Trade], None]) -> None:
        """Register a callback for trade updates."""
        self._callbacks['trades'].append(callback)

    def on_user_data(self, callback: Callable[[Dict], None]) -> None:
        """Register a callback for user data updates."""
        self._callbacks['user_data'].append(callback)

    async def connect(self) -> None:
        """Connect to the WebSocket server."""
        if self._ws is not None and not self._ws.closed:
            return

        self._running = True
        self._ws = await websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5
        )

        # Start the message handler
        asyncio.create_task(self._message_handler())

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._running = False
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
            self._ws = None

    async def _message_handler(self) -> None:
        """Handle incoming WebSocket messages."""
        try:
            while self._running and self._ws is not None and not self._ws.closed:
                try:
                    message = await self._ws.recv()
                    await self._process_message(json.loads(message))
                except websockets.exceptions.ConnectionClosed as e:
                    self._logger.warning(f"WebSocket connection closed: {e}")
                    if self._running:
                        await self._reconnect()
                    break
                except Exception as e:
                    self._logger.error(f"Error processing message: {e}", exc_info=True)
        except asyncio.CancelledError:
            self._logger.debug("Message handler was cancelled")
        except Exception as e:
            self._logger.error(f"Message handler failed: {e}", exc_info=True)

    async def _reconnect(self) -> None:
        """Reconnect to the WebSocket server and resubscribe to channels."""
        self._logger.info("Attempting to reconnect...")
        max_attempts = 5
        base_delay = 1.0

        for attempt in range(max_attempts):
            try:
                subscriptions = list(self._subscriptions)
                self._subscriptions.clear()

                await self.connect()

                # Resubscribe to all channels
                for channel in subscriptions:
                    await self.subscribe(channel)

                self._logger.info("Successfully reconnected and resubscribed")
                return

            except Exception as e:
                if attempt == max_attempts - 1:
                    self._logger.error(f"Failed to reconnect after {max_attempts} attempts: {e}")
                    raise WebSocketDisconnectedError("Failed to reconnect") from e

                delay = base_delay * (2 ** attempt)  # Exponential backoff
                self._logger.warning(f"Reconnect attempt {attempt + 1} failed, retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

    @abstractmethod
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """
        Process an incoming WebSocket message.

        Args:
            message: The received message as a dictionary
        """
        pass

    @abstractmethod
    async def subscribe(self, channel: str, **kwargs) -> None:
        """
        Subscribe to a channel.

        Args:
            channel: Channel to subscribe to (e.g., 'ticker.BTCUSDT')
            **kwargs: Additional parameters
        """
        pass

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """
        Unsubscribe from a channel.

        Args:
            channel: Channel to unsubscribe from
        """
        pass

    async def _run_callback(self, callback: Callable, *args, **kwargs) -> None:
        """
        Run a callback and handle any exceptions.

        Args:
            callback: The callback function to run
            *args: Positional arguments to pass to the callback
            **kwargs: Keyword arguments to pass to the callback
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                # Run synchronous callbacks in a thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, callback, *args, **kwargs)
        except Exception as e:
            self._logger.error(f"Error in callback: {e}", exc_info=True)