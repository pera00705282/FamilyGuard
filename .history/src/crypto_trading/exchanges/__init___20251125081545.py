"""Exchange connectors for various cryptocurrency exchanges.

This module provides a unified interface to interact with different cryptocurrency
exchanges. It includes a base exchange class that defines the common interface
and specific implementations for each supported exchange.
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from .base_exchange import (
    BaseExchange,
    Ticker,
    OrderBook,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthenticationError
)

try:
    from .exchange_factory import ExchangeFactory
    EXCHANGE_FACTORY_AVAILABLE = True
except ImportError:
    EXCHANGE_FACTORY_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("ExchangeFactory not available")

# Configure logger
logger = logging.getLogger(__name__)

# Import exchange implementations with error handling
try:
    from .binance_exchange import BinanceExchange
    BINANCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import BinanceExchange: {e}")
    BINANCE_AVAILABLE = False
    BinanceExchange = None  # type: ignore

try:
    from .poloniex_exchange import PoloniexExchange
    POLONIEX_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import PoloniexExchange: {e}")
    POLONIEX_AVAILABLE = False
    PoloniexExchange = None  # type: ignore

try:
    BYBIT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import BybitExchange: {e}")
    BYBIT_AVAILABLE = False
    BybitExchange = None  # type: ignore

try:
    BITGET_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import BitgetExchange: {e}")
    BITGET_AVAILABLE = False
    BitgetExchange = None  # type: ignore

# Import WebSocket clients with error handling
try:
    WEBSOCKET_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import WebSocket clients: {e}")
    WEBSOCKET_AVAILABLE = False
    # Create dummy classes to prevent import errors
    BaseWebSocketClient = object  # type: ignore
    BinanceWebSocketClient = None  # type: ignore
    PoloniexWebSocketClient = None  # type: ignore
    BybitWebSocketClient = None  # type: ignore
    BitgetWebSocketClient = None  # type: ignore

# Auto-register available exchanges
if BINANCE_AVAILABLE and BinanceExchange is not None:
    ExchangeFactory.register_exchange('binance', BinanceExchange)

if POLONIEX_AVAILABLE and PoloniexExchange is not None:
    ExchangeFactory.register_exchange('poloniex', PoloniexExchange)

if BYBIT_AVAILABLE and BybitExchange is not None:
    ExchangeFactory.register_exchange('bybit', BybitExchange)

if BITGET_AVAILABLE and BitgetExchange is not None and EXCHANGE_FACTORY_AVAILABLE:
    ExchangeFactory.register_exchange('bitget', BitgetExchange)

# Import interfaces
from .interfaces import (
    BaseExchangeClient,
    BaseWebSocketClient,
    TickerData,
    OrderBookData,
    TradeData,
    OrderInfo,
    OrderType,
    OrderSide,
    TimeInForce
)

# Only include available components in __all__
__all__ = [
    'BaseExchangeClient',
    'BaseWebSocketClient',
    'TickerData',
    'OrderBookData',
    'TradeData',
    'OrderInfo',
    'OrderType',
    'OrderSide',
    'TimeInForce',
    'ExchangeError',
    'BaseExchange',
    'Ticker',
    'OrderBook',
    'ExchangeConnectionError',
    'ExchangeAuthenticationError'
]

# Conditionally add factory if available
if EXCHANGE_FACTORY_AVAILABLE and ExchangeFactory is not None:
    __all__.append('ExchangeFactory')
# Conditionally add exchange implementations
if BINANCE_AVAILABLE and BinanceExchange is not None:
    __all__.append('BinanceExchange')

if POLONIEX_AVAILABLE and 'PoloniexExchange' in globals():
    __all__.append('PoloniexExchange')

if BYBIT_AVAILABLE and 'BybitExchange' in globals():
    __all__.append('BybitExchange')

if BITGET_AVAILABLE and 'BitgetExchange' in globals():
    __all__.append('BitgetExchange')

# Add WebSocket clients if available
if WEBSOCKET_AVAILABLE:
    ws_clients = ['BaseWebSocketClient']
    
    if BINANCE_AVAILABLE and 'BinanceWebSocketClient' in globals():
        ws_clients.append('BinanceWebSocketClient')
    if POLONIEX_AVAILABLE and 'PoloniexWebSocketClient' in globals():
        ws_clients.append('PoloniexWebSocketClient')
    if BYBIT_AVAILABLE and 'BybitWebSocketClient' in globals():
        ws_clients.append('BybitWebSocketClient')
    if BITGET_AVAILABLE and 'BitgetWebSocketClient' in globals():
        ws_clients.append('BitgetWebSocketClient')
        
    __all__.extend(ws_clients)
