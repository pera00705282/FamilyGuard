"""



Exchange connectors for various cryptocurrency exchanges.

This module provides a unified interface to interact with different cryptocurrency
exchanges. It includes a base exchange class that defines the common interface
and specific implementations for each supported exchange.
"""

    BaseExchange,
    Ticker,
    OrderBook,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthenticationError
)


# WebSocket clients

# Auto-register exchanges
ExchangeFactory.register_exchange('binance', BinanceExchange)
ExchangeFactory.register_exchange('poloniex', PoloniexExchange)
ExchangeFactory.register_exchange('bybit', BybitExchange)

__all__ = [
    # Base classes
    'BaseExchange',
    'BaseWebSocketClient',

    # Data models
    'Ticker',
    'OrderBook',

    # Exceptions
    'ExchangeError',
    'ExchangeConnectionError',
    'ExchangeAuthenticationError',

    # Factory
    'ExchangeFactory',

    # Exchange implementations
    'BinanceExchange',
    'PoloniexExchange',
    'BybitExchange',

    # WebSocket clients
    'BinanceWebSocketClient',
    'PoloniexWebSocketClient',
    'BybitWebSocketClient'
]