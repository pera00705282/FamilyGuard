"""Standardized interfaces for cryptocurrency exchange clients.

This module provides the core interfaces and data structures that define the contract
between different exchange implementations and the rest of the trading system.
It ensures consistent behavior and data formats across all supported exchanges.

Version: 1.0.0
Author: Crypto Trading Team

Key Features:
- Type-safe interfaces with comprehensive type hints
- Support for both REST and WebSocket APIs
- Standardized data structures for market data and orders
- Comprehensive error handling with custom exceptions
- Thread-safe and async/await compatible

Example:
    ```python
    from crypto_trading.exchanges import BaseExchangeClient, TickerData
    from decimal import Decimal
    
    class MyExchangeClient(BaseExchangeClient):
        async def get_ticker(self, symbol: str) -> TickerData:
            # Implementation here
            pass
    ```

For more examples and advanced usage, see the project's README.md
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import (
    Any, 
    AsyncGenerator, 
    Callable, 
    ClassVar, 
    Dict, 
    List, 
    Literal, 
    Optional, 
    Tuple, 
    Type, 
    TypeVar, 
    Union,
    overload
)

# Type aliases
Symbol = str
OrderId = str
TradeId = str
Asset = str
Timestamp = float
T = TypeVar('T')

# Callback types
TickerCallback = Callable[['TickerData'], None]
OrderBookCallback = Callable[['OrderBookData'], None]
TradeCallback = Callable[['TradeData'], None]
OrderCallback = Callable[['OrderInfo'], None]
ErrorCallback = Callable[[Exception], None]


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


@dataclass(frozen=True)
class OrderBookData:
    """Standardized order book data structure.

    Represents the current state of the order book (market depth) for a trading pair.
    Bids are buy orders (prices at which buyers are willing to purchase),
    while asks are sell orders (prices at which sellers are willing to sell).

    This is a frozen (immutable) dataclass to ensure thread-safety and
    prevent accidental modification of market data.

    Attributes:
        symbol: Trading pair symbol in format 'BASE/QUOTE' (e.g., 'BTC/USDT')
        bids: List of bid orders, each represented as (price, quantity) tuples,
              sorted from highest to lowest price (best bid first)
        asks: List of ask orders, each represented as (price, quantity) tuples,
              sorted from lowest to highest price (best ask first)
        timestamp: Unix timestamp in seconds when the order book was last updated
        sequence: Optional sequence number for tracking updates (exchange-specific)

    Example:
        ```python
        # Get order book for BTC/USDT with top 10 levels
        order_book = await exchange.get_order_book('BTC/USDT', limit=10)

        # Get best bid and ask prices
        best_bid = order_book.best_bid()
        best_ask = order_book.best_ask()

        # Calculate spread
        if best_bid and best_ask:
            spread = best_ask[0] - best_bid[0]
            spread_percent = (spread / best_bid[0]) * 100
            print(f"Spread: {spread:.2f} ({spread_percent:.2f}%)")

        # Calculate total bid/ask volume
        total_bid_volume = sum(qty for _, qty in order_book.bids)
        total_ask_volume = sum(qty for _, qty in order_book.asks)
        print(f"Total bid volume: {total_bid_volume}")
        print(f"Total ask volume: {total_ask_volume}")
        ```
    """
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    sequence: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate the order book data after initialization."""
        if not self.symbol or '/' not in self.symbol:
            raise ValueError(f"Invalid symbol format: {self.symbol}. Expected 'BASE/QUOTE' format.")
        
        if self.timestamp <= 0:
            raise ValueError(f"Invalid timestamp: {self.timestamp}")
            
        # Ensure bids are sorted in descending order (best bid first)
        if self.bids != sorted(self.bids, key=lambda x: -x[0]):
            object.__setattr__(self, 'bids', sorted(self.bids, key=lambda x: -x[0]))
            
        # Ensure asks are sorted in ascending order (best ask first)
        if self.asks != sorted(self.asks, key=lambda x: x[0]):
            object.__setattr__(self, 'asks', sorted(self.asks, key=lambda x: x[0]))

    def best_bid(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Get the best (highest) bid price and quantity.
        
        Returns:
            Optional[Tuple[Decimal, Decimal]]: (price, quantity) of best bid, or None if no bids
        """
        return self.bids[0] if self.bids else None

    def best_ask(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Get the best (lowest) ask price and quantity.
        
        Returns:
            Optional[Tuple[Decimal, Decimal]]: (price, quantity) of best ask, or None if no asks
        """
        return self.asks[0] if self.asks else None

    def get_mid_price(self) -> Optional[Decimal]:
        """Calculate the mid price between best bid and ask.
        
        Returns:
            Optional[Decimal]: Mid price, or None if either bid or ask is missing
        """
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        
        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / Decimal('2')
        return None

    def get_imbalance(self, levels: int = 10) -> Optional[Decimal]:
        """Calculate the order book imbalance.
        
        Args:
            levels: Number of price levels to consider
            
        Returns:
            Optional[Decimal]: Imbalance ratio between -1 and 1, or None if no data
                              Positive values indicate buying pressure,
                              negative values indicate selling pressure
        """
        if not self.bids or not self.asks:
            return None
            
        top_bids = self.bids[:levels]
        top_asks = self.asks[:levels]
        
        total_bid_volume = sum(qty for _, qty in top_bids)
        total_ask_volume = sum(qty for _, qty in top_asks)
        total_volume = total_bid_volume + total_ask_volume
        
        if total_volume == 0:
            return None
            
        return (total_bid_volume - total_ask_volume) / total_volume

    def to_dict(self) -> Dict[str, Any]:
        """Convert the order book to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the order book
        """
        return {
            'symbol': self.symbol,
            'bids': [(float(price), float(qty)) for price, qty in self.bids],
            'asks': [(float(price), float(qty)) for price, qty in self.asks],
            'timestamp': self.timestamp,
            'sequence': self.sequence
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBookData':
        """Create an OrderBookData instance from a dictionary.
        
        Args:
            data: Dictionary containing order book data
            
        Returns:
            OrderBookData: A new OrderBookData instance
        """
        return cls(
            symbol=data['symbol'],
            bids=[(Decimal(str(price)), Decimal(str(qty))) for price, qty in data['bids']],
            asks=[(Decimal(str(price)), Decimal(str(qty))) for price, qty in data['asks']],
            timestamp=data.get('timestamp', datetime.utcnow().timestamp()),
            sequence=data.get('sequence')
        )


@dataclass
class TradeData:
    """Standardized trade data structure representing a single trade execution.

    This class provides a normalized representation of trade data across different
    exchanges, making it easier to process and analyze trading activity.

    Attributes:
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        price: Execution price of the trade
        quantity: Quantity of the base currency that was traded
        side: Whether the trade was a buy or sell from the taker's perspective
        timestamp: Unix timestamp in seconds when the trade occurred
        trade_id: Unique identifier for the trade (exchange-specific)

    Example:
        ```python
        # Process recent trades
        trades = await exchange.get_recent_trades('BTC/USDT', limit=5)
        for trade in trades:
            print(f"{trade.symbol} - {trade.side.upper()} {trade.quantity} @ {trade.price}")

        # Calculate total volume for the last 100 trades
        recent_trades = await exchange.get_recent_trades('BTC/USDT', limit=100)
        total_volume = sum(trade.quantity * trade.price for trade in recent_trades)
        print(f"24h volume in USDT: {total_volume}")
        ```
    """
    symbol: str
    price: Decimal
    quantity: Decimal
    side: OrderSide
    timestamp: float
    trade_id: str


@dataclass
class OrderInfo:
    """Comprehensive order information and status.

    Represents the state of an order in the exchange's matching engine.
    This class provides a normalized view of order information across different exchanges.

    Attributes:
        order_id: Unique identifier for the order (exchange-specific)
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        side: Whether the order is to buy or sell
        order_type: Type of the order (market, limit, stop-loss, etc.)
        price: Limit price for the order (None for market orders)
        quantity: Total quantity of the order in base currency
        filled_quantity: Quantity that has been filled so far
        status: Current status of the order. Common values include:
               - 'NEW': Order has been accepted by the exchange
               - 'PARTIALLY_FILLED': Part of the order has been filled
               - 'FILLED': Order has been completely filled
               - 'CANCELED': Order has been canceled
               - 'REJECTED': Order was rejected by the exchange
               - 'EXPIRED': Order expired (time in force)
        time_in_force: Specifies how long the order remains active
        created_at: Timestamp when the order was created (Unix timestamp in seconds)
        updated_at: Timestamp when the order was last updated (Unix timestamp in seconds)

    Example:
        ```python
        # Place a limit order
        order = await exchange.create_order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal('0.1'),
            price=Decimal('50000.00')
        )

        # Check order status
        order_info = await exchange.get_order(order.order_id, 'BTC/USDT')
        print(f"Order {order_info.status}")
        print(f"Filled: {order_info.filled_quantity}/{order_info.quantity}")

        # Cancel the order if not filled
        if order_info.status in ['NEW', 'PARTIALLY_FILLED']:
            await exchange.cancel_order(order_info.order_id, 'BTC/USDT')
        ```
    """
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    status: str = 'NEW'
    time_in_force: TimeInForce = TimeInForce.GTC
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


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
    """Abstract base class for real-time WebSocket clients.

    This class defines the interface for WebSocket clients that handle real-time
    market data and user updates. Implementations should handle connection
    management, subscriptions, and message parsing.

    Note:
        All callbacks are called asynchronously and should be defined as async functions.
        The WebSocket client should automatically handle reconnection on connection loss.

    Example:
        ```python
        class MyWebSocketClient(BaseWebSocketClient):
            async def connect(self):
                # Implementation for establishing WebSocket connection
                pass

            async def on_ticker(self, callback):
                # Implementation for subscribing to ticker updates
                pass

        # Usage:
        async def handle_ticker_update(ticker: TickerData):
            print(f"{ticker.symbol} - Last: {ticker.last}")

        ws_client = MyWebSocketClient()
        await ws_client.connect()
        await ws_client.on_ticker(handle_ticker_update)
        ```
    """
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
    """Base exception for all exchange-related errors.

    This is the parent class for all exceptions raised by exchange clients.
    It should be used to catch any exchange-related errors in a generic way.
    
    Example:
        ```python
        try:
            await exchange.create_order(...)
        except ExchangeError as e:
            print(f"Exchange error: {e}")
        ```
    """
    pass


class ExchangeNotAvailable(ExchangeError):
    """Raised when the exchange API is not available or unresponsive.

    This exception typically indicates network issues, maintenance, or downtime
    on the exchange's side. The operation might succeed if retried later.
    
    Example:
        ```python
        try:
            await exchange.get_ticker('BTC/USDT')
        except ExchangeNotAvailable as e:
            print("Exchange is currently unavailable. Please try again later.")
            # Consider implementing a retry mechanism with exponential backoff
        ```
    """
    pass


class RateLimitExceeded(ExchangeError):
    """Raised when the rate limit for the exchange API is exceeded.

    This exception indicates that the client has made too many requests
    in a short period. The client should implement rate limiting and
    retry the request after the appropriate cooldown period.

    Example:
        ```python
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type(RateLimitExceeded)
        )
        async def get_ticker_with_retry(exchange, symbol):
            return await exchange.get_ticker(symbol)
        ```
    """
    pass


class InvalidOrder(ExchangeError):
    """Raised when an order is invalid or cannot be processed.

    Common reasons for this error include:
    - Insufficient funds
    - Invalid symbol
    - Incorrect price/quantity precision
    - Unsupported order type for the trading pair

    The error message should provide specific details about why the order was rejected.

    Example:
        ```python
        try:
            # Attempt to place an order with invalid parameters
            await exchange.create_order(
                symbol='NONEXISTENT/PAIR',
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal('0.1')
            )
        except InvalidOrder as e:
            print(f"Order rejected: {e}")
        ```
    """
    pass


class AuthenticationError(ExchangeError):
    """Raised when API authentication fails.

    This exception indicates that the provided API credentials are invalid,
    have insufficient permissions, or have expired.
    
    Example:
        ```python
        try:
            # Initialize client with invalid credentials
            client = BinanceExchange(api_key='invalid', api_secret='invalid')
            await client.get_balance()
        except AuthenticationError as e:
            print("Authentication failed. Please check your API credentials.")
            # Consider prompting the user to update their credentials
        ```
    """
    pass
