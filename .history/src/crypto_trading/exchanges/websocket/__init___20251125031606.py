


""
WebSocket clients for cryptocurrency exchanges.

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

from .binance_websocket import BinanceWebSocketClient

__all__ = [
    'BaseWebSocketClient',
    'TickerUpdate',
    'OrderBookUpdate',
    'Trade',
    'WebSocketError',
    'WebSocketConnectionError',
    'WebSocketSubscriptionError',
    'BinanceWebSocketClient',
]