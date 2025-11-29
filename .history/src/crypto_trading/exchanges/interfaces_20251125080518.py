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
    """Base interface for all exchange clients.

    This abstract base class defines the standard interface that all exchange
    implementations must follow to ensure consistent behavior.
    """
    @abstractmethod
    async def get_ticker(self, symbol: str) -> 'TickerData':
        """Get current ticker information for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            TickerData: Standardized ticker data

        Raises:
            ExchangeError: If the request fails
        """
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 100) -> 'OrderBookData':
        """Get order book for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of orders to return (default: 100)

        Returns:
            OrderBookData: Standardized order book data
        """
        pass
    
    @abstractmethod
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List['TradeData']:
        """Get recent trades for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Maximum number of trades to return (default: 100)

        Returns:
            List[TradeData]: List of recent trades
        """
        pass
    
    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        order_type: 'OrderType',
        side: 'OrderSide',
        quantity: Decimal,
        price: Optional[Decimal] = None,
        **params
    ) -> 'OrderInfo':
        """Create a new order.

        Args:
            symbol: Trading pair symbol
            order_type: Type of order (market, limit, etc.)
            side: Order side (buy/sell)
            quantity: Order quantity
            price: Order price (required for limit orders)
            **params: Additional order parameters

        Returns:
            OrderInfo: Information about the created order
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> 'OrderInfo':
        """Get order information.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            OrderInfo: Information about the order
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            bool: True if order was successfully canceled
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
