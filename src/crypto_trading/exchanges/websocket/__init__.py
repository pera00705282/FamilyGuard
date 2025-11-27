"""WebSocket clients for cryptocurrency exchanges.

This package provides WebSocket clients for various cryptocurrency exchanges,
allowing real-time data streaming for market data, order book updates,
and user account events.
"""

from .base_websocket import (
    BaseWebSocketClient,
    TickerUpdate,
    OrderBookUpdate,
    Trade,
    WebSocketError,
    WebSocketConnectionError,
    WebSocketSubscriptionError,
)

# Import WebSocket clients for different exchanges
try:
    from .binance_websocket import BinanceWebSocketClient
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False

try:
    from .poloniex_websocket import PoloniexWebSocketClient
    POLONIEX_AVAILABLE = True
except ImportError:
    POLONIEX_AVAILABLE = False

# Define __all__ with available modules
__all__ = [
    # Base classes
    'BaseWebSocketClient',

    # Data models
    'TickerUpdate',
    'OrderBookUpdate',
    'Trade',

    # Exceptions
    'WebSocketError',
    'WebSocketConnectionError',
    'WebSocketSubscriptionError',
]

# Add exchange-specific clients if available
if BINANCE_AVAILABLE:
    __all__.append('BinanceWebSocketClient')

if POLONIEX_AVAILABLE:
    __all__.append('PoloniexWebSocketClient')