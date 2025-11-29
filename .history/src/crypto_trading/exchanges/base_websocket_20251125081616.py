"""Base WebSocket client for exchange connections.

This module provides a base class for implementing WebSocket clients
for various cryptocurrency exchanges.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Set

logger = logging.getLogger(__name__)


class BaseWebSocketClient(ABC):
    """Base class for WebSocket clients."""

    def __init__(self, **kwargs) -> None:
        """Initialize the WebSocket client.

        Args:
            **kwargs: Additional arguments for specific implementations
        """
        self._ws = None
        self._callbacks: Dict[str, Set[Callable]] = {
            'ticker': set(),
            'order_book': set(),
            'trade': set(),
            'order': set(),
            'account': set(),
            'error': set()
        }
        self._is_connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 1  # Start with 1 second delay
        self._max_reconnect_delay = 30  # Max 30 seconds delay

    @abstractmethod
    async def connect(self) -> None:
        """Establish WebSocket connection.
        
        Raises:
            ConnectionError: If connection cannot be established
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        pass

    async def _notify(self, event_type: str, symbol: str, data: Any) -> None:
        """Notify all registered callbacks for an event.

        Args:
            event_type: Type of event (ticker, order_book, trade, order, account)
            symbol: Trading pair symbol
            data: Event data
        """
        if event_type not in self._callbacks:
            logger.warning(f"Unknown event type: {event_type}")
            return
            
        for callback in self._callbacks[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(symbol, data)
                else:
                    # Run synchronous callbacks in executor
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, callback, symbol, data)
            except Exception as e:
                logger.error(f"Error in {event_type} callback: {e}", exc_info=True)

    def register_callback(
        self,
        event_type: str,
        callback: Callable[[str, Any], None]
    ) -> None:
        """Register a callback function for a specific event type.

        Args:
            event_type: Type of event (ticker, order_book, trade, order, account)
            callback: Callback function that takes (symbol, data) as arguments

        Raises:
            ValueError: If event_type is not supported
        """
        if event_type not in self._callbacks:
            raise ValueError(f"Unsupported event type: {event_type}")
        self._callbacks[event_type].add(callback)

    def unregister_callback(
        self,
        event_type: str,
        callback: Callable[[str, Any], None]
    ) -> None:
        """Unregister a callback function.

        Args:
            event_type: Type of event
            callback: Callback function to unregister
        """
        self._callbacks[event_type].discard(callback)

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            await self._notify('error', 'connection', "Max reconnection attempts reached")
            return

        delay = min(
            self._reconnect_delay * (2 ** self._reconnect_attempts),
            self._max_reconnect_delay
        )

        logger.info(
            f"Reconnecting in {delay:.1f} seconds... "
            f"(attempt {self._reconnect_attempts + 1}/{self._max_reconnect_attempts})"
        )
        await asyncio.sleep(delay)

        try:
            await self.connect()
            self._reconnect_attempts = 0
            self._reconnect_delay = 1
        except Exception as e:
            self._reconnect_attempts += 1
            logger.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")
            await self._reconnect()

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._is_connected

    @abstractmethod
    async def subscribe_ticker(self, symbol: str) -> None:
        """Subscribe to ticker updates for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
        """
        pass

    @abstractmethod
    async def subscribe_order_book(self, symbol: str) -> None:
        """Subscribe to order book updates for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
        """
        pass

    @abstractmethod
    async def subscribe_trades(self, symbol: str) -> None:
        """Subscribe to trade updates for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
        """
        pass

    @abstractmethod
    async def subscribe_user_data(self) -> None:
        """Subscribe to user data updates (orders, account, etc.)."""
        pass
