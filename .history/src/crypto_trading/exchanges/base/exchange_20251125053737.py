"""Base exchange module defining the abstract interface for all exchange implementations."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

class ExchangeError(Exception):
    """Base exception for all exchange-related errors."""
    pass


class ExchangeConnectionError(ExchangeError):
    """Raised when there is a problem connecting to the exchange."""
    pass


class ExchangeAuthenticationError(ExchangeError):
    """Raised when authentication with the exchange fails."""
    pass


class OrderBook:
    """Represents an order book for a trading pair."""

    def __init__(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], timestamp: float):
        """
        Initialize order book.

        Args:
            bids: List of bid tuples (price, amount)
            asks: List of ask tuples (price, amount)
            timestamp: Unix timestamp of the order book
        """
        self.bids = sorted(((Decimal(str(price)), Decimal(str(amount)))
                          for price, amount in bids), reverse=True)
        self.asks = sorted(((Decimal(str(price)), Decimal(str(amount)))
                          for price, amount in asks))
        self.timestamp = timestamp


class Ticker:
    """Represents ticker information for a trading pair."""

    def __init__(self, symbol: str, bid: Union[float, Decimal, str],
                 ask: Union[float, Decimal, str], last: Union[float, Decimal, str],
                 base_volume: Union[float, Decimal, str],
                 quote_volume: Union[float, Decimal, str],
                 timestamp: float):
        """
        Initialize ticker.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            bid: Current best bid price
            ask: Current best ask price
            last: Last traded price
            base_volume: 24h trading volume in base currency
            quote_volume: 24h trading volume in quote currency
            timestamp: Unix timestamp of the ticker
        """
        self.symbol = symbol
        self.bid = Decimal(str(bid))
        self.ask = Decimal(str(ask))
        self.last = Decimal(str(last))
        self.base_volume = Decimal(str(base_volume))
        self.quote_volume = Decimal(str(quote_volume))
        self.timestamp = timestamp


class BaseExchange(ABC):
    """Abstract base class for all exchange implementations."""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        """
        Initialize the exchange.

        Args:
            api_key: API key for the exchange
            api_secret: API secret for the exchange
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.name = ""
        self._session = None

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
            Dictionary mapping currency codes to available balance
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
            limit: Maximum number of orders to return for each side

        Returns:
            OrderBook object with bids and asks
        """
        pass

    @abstractmethod
    async def create_order(self, symbol: str, order_type: str, side: str,
                         amount: Decimal, price: Optional[Decimal] = None) -> Dict:
        """
        Create a new order.

        Args:
            symbol: Trading pair symbol
            order_type: Order type (e.g., 'market', 'limit')
            side: Order side ('buy' or 'sell')
            amount: Order amount in base currency
            price: Order price (required for limit orders)

        Returns:
            Order details
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get list of open orders.

        Args:
            symbol: Optional trading pair symbol to filter orders

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
            True if cancellation was successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_markets(self) -> List[Dict]:
        """
        Get list of available markets and their details.

        Returns:
            List of market dictionaries with trading pair information
        """
        pass