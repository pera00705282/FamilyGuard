"""






Base WebSocket client for exchange connections.
"""
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

@dataclass


class TickerUpdate:
    """Represents a ticker price update."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    timestamp: float

@dataclass
class OrderBookUpdate:
    """Represents an order book update."""
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]  # [(price, amount), ...]
    asks: List[Tuple[Decimal, Decimal]]  # [(price, amount), ...]
    timestamp: float

@dataclass


class Trade:
    """Represents a trade."""
    symbol: str
    price: Decimal
    amount: Decimal
    side: str  # 'buy' or 'sell'
    timestamp: float
    trade_id: Optional[str] = None

class WebSocketError(Exception):
    """Base exception for WebSocket related errors."""
    pass

class WebSocketConnectionError(WebSocketError):
    """Raised when there is a connection error."""
    pass

class WebSocketSubscriptionError(WebSocketError):
    """Raised when there is an error subscribing to a channel."""
    pass

class BaseWebSocketClient(ABC):
    """Base WebSocket client for exchange connections."""

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        reconnect_interval: int = 15,
        max_reconnect_attempts: int = 10,
        ping_interval: int = 20,
        ping_timeout: int = 10,
    ):
        """Initialize the WebSocket client.

        Args:
            url: WebSocket URL
            api_key: API key for private channels
            api_secret: API secret for private channels
            reconnect_interval: Time to wait between reconnection attempts (seconds)
            max_reconnect_attempts: Maximum number of reconnection attempts
            ping_interval: Interval for sending ping messages (seconds)
            ping_timeout: Time to wait for pong response (seconds)
        """
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        self._ws: Optional[WebSocketClientProtocol] = None
        self._reconnect_attempts = 0
        self._should_reconnect = True
        self._subscriptions: Set[str] = set()
        self._callbacks = {
            'ticker': [],
            'orderbook': [],
            'trades': [],
            'user_data': [],
            'error': [],
        }
        self._last_pong = time.time()
        self._ping_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None

    def on_ticker(self, callback: Callable[[TickerUpdate], None]) -> None:
        """Register a callback for ticker updates."""
        self._callbacks['ticker'].append(callback)

    def on_orderbook(self, callback: Callable[[OrderBookUpdate], None]) -> None:
        """Register a callback for order book updates."""
        self._callbacks['orderbook'].append(callback)

    def on_trades(self, callback: Callable[[Trade], None]) -> None:
        """Register a callback for trade updates."""
        self._callbacks['trades'].append(callback)

    def on_user_data(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for user data updates."""
        self._callbacks['user_data'].append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register a callback for errors."""
        self._callbacks['error'].append(callback)

    async def connect(self) -> None:
        """Connect to the WebSocket server and start the message loop."""
        self._should_reconnect = True
        await self._connect()

    async def _connect(self) -> None:
        """Establish WebSocket connection and start tasks."""
        try:
            logger.info(f"Connecting to WebSocket at {self.url}")
            self._ws = await websockets.connect(
                self.url,
                ping_interval=None,  # We'll handle pings manually
                close_timeout=1,
                max_queue=1024,
            )

            self._reconnect_attempts = 0

            # Start the ping task
            self._ping_task = asyncio.create_task(self._ping_loop())

            # Start the consumer task
            self._consumer_task = asyncio.create_task(self._consumer())

            # Resubscribe to channels if reconnecting
            if self._subscriptions:
                await self._resubscribe()

            logger.info("WebSocket connected successfully")

        except Exception as e:
            await self._handle_error(f"Failed to connect: {str(e)}")
            await self._schedule_reconnect()

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._should_reconnect = False

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

    async def _ping_loop(self) -> None:
        """Send periodic ping messages to keep the connection alive."""
        while self._ws and self._ws.open:
            try:
                await asyncio.sleep(self.ping_interval)
                if self._ws and self._ws.open:
                    await self._ws.ping()
                    # Wait for pong with timeout
                    start_time = time.time()
                    while time.time() - start_time < self.ping_timeout:
                        if self._last_pong >= start_time:
                            break
                        await asyncio.sleep(0.1)
                    else:
                        # No pong received within timeout
                        logger.warning("No pong received, reconnecting...")
                        await self._reconnect()
                        return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
                await self._handle_error(f"Ping error: {str(e)}")
                await self._schedule_reconnect()
                return

    async def _consumer(self) -> None:
        """Process incoming WebSocket messages."""
        while self._ws and self._ws.open:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_connection_closed()
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._handle_error(f"Error processing message: {str(e)}")

    async def _handle_connection_closed(self) -> None:
        """Handle WebSocket connection closed event."""
        await self._schedule_reconnect()

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if not self._should_reconnect or self._reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached, giving up")
            return

        self._reconnect_attempts += 1
        wait_time = min(self.reconnect_interval * (2 ** (self._reconnect_attempts - 1)), 300)

        logger.info(f"Attempting to reconnect in {wait_time} seconds (attempt {self._reconnect_attempts}/{self.max_reconnect_attempts})")

        await asyncio.sleep(wait_time)
        await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect to the WebSocket server."""
        await self.disconnect()
        await self._connect()

    async def _resubscribe(self) -> None:
        """Resubscribe to all channels after reconnection."""
        if not self._subscriptions:
            return

        logger.info(f"Resubscribing to {len(self._subscriptions)} channels")

        # Convert set to list to avoid modification during iteration
        subscriptions = list(self._subscriptions)
        self._subscriptions.clear()

        for channel in subscriptions:
            try:
                await self.subscribe(channel)
            except Exception as e:
                await self._handle_error(f"Failed to resubscribe to {channel}: {str(e)}")

    async def _handle_message(self, message: Union[str, bytes]) -> None:
        """Handle incoming WebSocket message.

        Args:
            message: The raw message from the WebSocket
        """
        try:
            if isinstance(message, bytes):
                message = message.decode('utf-8')

            data = json.loads(message)

            # Update last pong time if this is a pong message
            if 'pong' in str(data).lower():
                self._last_pong = time.time()
                return

            # Let the subclass handle the message
            await self._process_message(data)

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse message as JSON: {message}")
        except Exception as e:
            await self._handle_error(f"Error processing message: {str(e)}\nMessage: {message}")

    async def _handle_error(self, error_msg: str, exc: Optional[Exception] = None) -> None:
        """Handle errors and notify callbacks."""
        error = exc or Exception(error_msg)
        logger.error(error_msg, exc_info=exc)

        for callback in self._callbacks['error']:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}", exc_info=True)

    @abstractmethod
    async def subscribe(self, channel: str, **kwargs) -> None:
        """Subscribe to a channel.

        Args:
            channel: The channel to subscribe to (e.g., 'ticker.BTC-USDT')
            **kwargs: Additional parameters for the subscription
        """
        pass

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: The channel to unsubscribe from
        """
        pass

    @abstractmethod
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an incoming WebSocket message.

        Args:
            message: The parsed message
        """
        pass

    @abstractmethod
    async def authenticate(self) -> None:
        """Authenticate the WebSocket connection."""
        pass