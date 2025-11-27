"""Base exchange interface and common types for crypto trading."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

@dataclass
class Ticker:
    """Represents ticker data for a trading pair."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    timestamp: float

@dataclass
class OrderBook:
    """Represents an order book with bids and asks."""
    bids: List[Tuple[Decimal, Decimal]]  # (price, amount)
    asks: List[Tuple[Decimal, Decimal]]  # (price, amount)
    timestamp: float

class ExchangeError(Exception):
    """Base exception for all exchange-related errors."""
    pass

class ExchangeConnectionError(ExchangeError):
    """Raised when there is a problem connecting to the exchange."""
    pass

class ExchangeAuthenticationError(ExchangeError):
    """Raised when there is an authentication error with the exchange."""
    pass

class BaseExchange(ABC):
    """Base class for all exchange connectors."""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        """
        Initialize the exchange connector.

        Args:
            api_key: API key for the exchange
            api_secret: API secret for the exchange
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.name = self.__class__.__name__.replace('Exchange', '').lower()
        self._session = None
        self._rate_limit_semaphore = None
        self._last_request_time = 0
        self.rate_limit_delay = 1.0  # Default rate limit delay in seconds

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to the exchange."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the exchange."""
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, Decimal]:
        """
        Get account balances.

        Returns:
            Dict with currency as key and available balance as value
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """
        Get ticker information for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            Ticker object with market data
        """
        pass

    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        """
        Get order book for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of orders to return

        Returns:
            OrderBook object with bids and asks
        """
        pass

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None
    ) -> dict:
        """
        Create a new order.

        Args:
            symbol: Trading pair symbol
            order_type: Order type (e.g., 'limit', 'market')
            side: 'buy' or 'sell'
            amount: Amount to trade
            price: Price for limit orders

        Returns:
            Order information
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        Get list of open orders.

        Args:
            symbol: Optional trading pair symbol to filter by

        Returns:
            List of open orders
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: ID of the order to cancel
            symbol: Trading pair symbol

        Returns:
            True if order was cancelled successfully, False otherwise
        """
        pass

    @abstractmethod
    async def get_markets(self) -> List[dict]:
        """
        Get list of available markets and their details.

        Returns:
            List of market dictionaries with trading pair details
        """
        pass

    def __str__(self):
        return f"{self.name} Exchange Connector"

    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}')>"