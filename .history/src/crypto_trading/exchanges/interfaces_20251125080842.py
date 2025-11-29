"""
Standardized interfaces for exchange clients.

This module defines the base interfaces that all exchange implementations
must follow to ensure consistent behavior across different exchanges.
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class OrderType(str, Enum):
    """Supported order types across exchanges."""
    MARKET = 'market'
    LIMIT = 'limit'
    STOP_LOSS = 'stop_loss'
    TAKE_PROFIT = 'take_profit'
    STOP_LOSS_LIMIT = 'stop_loss_limit'
    TAKE_PROFIT_LIMIT = 'take_profit_limit'


class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = 'buy'
    SELL = 'sell'


class TimeInForce(str, Enum):
    """Time in force for orders."""
    GTC = 'GTC'  # Good Till Cancel
    IOC = 'IOC'   # Immediate or Cancel
    FOK = 'FOK'   # Fill or Kill
    GTD = 'GTD'   # Good Till Date (not supported by all exchanges)


@dataclass
class TickerData:
    """Standardized ticker data structure."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    timestamp: float  # Unix timestamp in seconds


@dataclass
class OrderBookData:
    """Standardized order book data structure."""
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]  # [(price, quantity), ...]
    asks: List[Tuple[Decimal, Decimal]]  # [(price, quantity), ...]
    timestamp: float  # Unix timestamp in seconds


@dataclass
class TradeData:
    """Standardized trade data structure."""
    symbol: str
    price: Decimal
    quantity: Decimal
    side: OrderSide
    timestamp: float  # Unix timestamp in seconds
    trade_id: str


@dataclass
class OrderInfo:
    """Standardized order information."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    status: str = 'NEW'  # NEW, PARTIALLY_FILLED, FILLED, CANCELED, etc.
    time_in_force: TimeInForce = TimeInForce.GTC
    created_at: Optional[float] = None  # Unix timestamp in seconds
    updated_at: Optional[float] = None  # Unix timestamp in seconds


class BaseExchangeClient(ABC):
    """Base class for exchange clients.

    This class defines the interface that all exchange clients must implement.
    """

    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerData:
        """Get the current ticker information for a symbol.

        Args:
            symbol: The trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            TickerData: The ticker data
        """
        pass

    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 100) -> OrderBookData:
        """Get the order book for a symbol.

        Args:
            symbol: The trading pair symbol
            limit: Maximum number of order book entries to return

        Returns:
            OrderBookData: The order book data
        """
        pass

    @abstractmethod
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[TradeData]:
        """Get recent trades for a symbol.

        Args:
            symbol: The trading pair symbol
            limit: Maximum number of trades to return

        Returns:
            List[TradeData]: List of recent trades
        """
        pass

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        **kwargs
    ) -> OrderInfo:
        """Create a new order.

        Args:
            symbol: The trading pair symbol
            side: Order side (buy/sell)
            order_type: Type of order (market/limit/stop_loss/etc.)
            quantity: Order quantity
            price: Order price (required for limit orders)
            time_in_force: Time in force for the order
            **kwargs: Additional order parameters

        Returns:
            OrderInfo: Information about the created order
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order.

        Args:
            order_id: The ID of the order to cancel
            symbol: The trading pair symbol

        Returns:
            bool: True if the order was successfully canceled, False otherwise
        """
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[OrderInfo]:
        """Get information about a specific order.

        Args:
            order_id: The ID of the order
            symbol: The trading pair symbol

        Returns:
            Optional[OrderInfo]: Order information if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderInfo]:
        """Get a list of open orders.

        Args:
            symbol: Optional trading pair symbol to filter by

        Returns:
            List[OrderInfo]: List of open orders
        """
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balance.

        Returns:
            Dict[str, Decimal]: Dictionary of asset balances
        """
        pass


class BaseWebSocketClient(ABC):
    """Base interface for WebSocket clients."""
    @abstractmethod
    async def connect(self) -> None:
        """Establish WebSocket connection."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        pass
    
    @abstractmethod
    def on_ticker(self, callback) -> None:
        """Register callback for ticker updates.

        Args:
            callback: Async function that receives TickerData
        """
        pass
    
    @abstractmethod
    def on_order_book(self, callback) -> None:
        """Register callback for order book updates.

        Args:
            callback: Async function that receives OrderBookData
        """
        pass
    
    @abstractmethod
    def on_trade(self, callback) -> None:
        """Register callback for trade updates.

        Args:
            callback: Async function that receives TradeData
        """
        pass


class ExchangeError(Exception):
    """Base exception for exchange-related errors."""
    pass


class ExchangeNotAvailable(ExchangeError):
    """Raised when the exchange API is not available."""
    pass


class RateLimitExceeded(ExchangeError):
    """Raised when rate limits are exceeded."""
    pass


class InvalidOrder(ExchangeError):
    """Raised when an order is invalid."""
    pass


class AuthenticationError(ExchangeError):
    """Raised when authentication fails."""
    pass
