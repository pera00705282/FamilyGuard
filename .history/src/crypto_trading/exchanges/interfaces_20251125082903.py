"""Standardized interfaces for cryptocurrency exchange clients.

This module provides the core interfaces and data structures that define the contract
between different exchange implementations and the rest of the trading system.
It ensures consistent behavior and data formats across all supported exchanges.

The module includes:
- Standard order types and trading enums
- Data structures for market data (tickers, order books, trades)
- Base classes for exchange clients and WebSocket clients
- Common exceptions for error handling

Example:
    ```python
    # Example of using the base exchange client
    class MyExchangeClient(BaseExchangeClient):
        async def get_ticker(self, symbol: str) -> TickerData:
            # Implementation here
            pass
    ```
"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum


class OrderType(str, Enum):
    """Supported order types across exchanges.

    Attributes:
        MARKET: Market order (executed immediately at best available price)
        LIMIT: Limit order (executed at specified price or better)
        STOP_LOSS: Stop loss order (becomes market order when stop price is reached)
        TAKE_PROFIT: Take profit order (becomes market order when take profit price is reached)
        STOP_LOSS_LIMIT: Stop loss limit order (becomes limit order when stop price is reached)
        TAKE_PROFIT_LIMIT: Take profit limit order (becomes limit order when take profit price is reached)

    Example:
        ```python
        # Place a limit buy order
        await exchange.create_order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal('0.01'),
            price=Decimal('50000.00')
        )
        ```
    """
    MARKET = 'market'
    LIMIT = 'limit'
    STOP_LOSS = 'stop_loss'
    TAKE_PROFIT = 'take_profit'
    STOP_LOSS_LIMIT = 'stop_loss_limit'
    TAKE_PROFIT_LIMIT = 'take_profit_limit'


class OrderSide(str, Enum):
    """Order side indicating whether to buy or sell an asset.

    Attributes:
        BUY: Buy order (acquiring the base currency)
        SELL: Sell order (disposing of the base currency)
    """
    BUY = 'buy'
    SELL = 'sell'


class TimeInForce(str, Enum):
    """Time in force specifies how long an order remains active.

    Attributes:
        GTC: Good Till Cancel - Order remains active until explicitly canceled
        IOC: Immediate or Cancel - Order must execute immediately or be canceled
        FOK: Fill or Kill - Order must execute completely or be canceled
        GTD: Good Till Date - Order remains active until a specified date/time
             (Note: Not all exchanges support GTD)

    Example:
        ```python
        # Place a limit order that will be canceled if not filled immediately
        await exchange.create_order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal('0.01'),
            price=Decimal('50000.00'),
            time_in_force=TimeInForce.IOC
        )
        ```
    """
    GTC = 'GTC'  # Good Till Cancel
    IOC = 'IOC'   # Immediate or Cancel
    FOK = 'FOK'   # Fill or Kill
    GTD = 'GTD'   # Good Till Date (not supported by all exchanges)


@dataclass
class TickerData:
    """Standardized ticker data structure.

    Represents the current market state for a trading pair.

    Attributes:
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        bid: Current highest bid price
        ask: Current lowest ask price
        last: Price of the most recent trade
        base_volume: 24h trading volume in the base currency
        quote_volume: 24h trading volume in the quote currency
        timestamp: Unix timestamp in seconds when the ticker was updated

    Example:
        ```python
        ticker = await exchange.get_ticker('BTC/USDT')
        print(f"BTC/USDT - Bid: {ticker.bid}, Ask: {ticker.ask}, 24h Volume: {ticker.base_volume} BTC")
        ```
    """
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    timestamp: float


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
    """Abstract base class defining the interface for exchange clients.

    This class specifies the contract that all exchange implementations must follow,
    ensuring consistent behavior across different cryptocurrency exchanges.
    Implementations should inherit from this class and override all abstract methods.

    Note:
        All methods are asynchronous and should be awaited when called.
        Implementations should handle rate limiting, retries, and error handling.

    Example:
        ```python
        class MyExchangeClient(BaseExchangeClient):
            def __init__(self, api_key: str, api_secret: str):
                self.api_key = api_key
                self.api_secret = api_secret
                # Initialize exchange-specific client

            async def get_ticker(self, symbol: str) -> TickerData:
                # Implementation here
                pass
        ```
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
