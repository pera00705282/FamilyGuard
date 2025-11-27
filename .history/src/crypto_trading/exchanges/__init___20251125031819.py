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


# Auto-register exchanges
ExchangeFactory.register('binance', BinanceExchange)
ExchangeFactory.register('poloniex', PoloniexExchange)

__all__ = [
    'BaseExchange',
    'Ticker',
    'OrderBook',
    'ExchangeError',
    'ExchangeConnectionError',
    'ExchangeAuthenticationError',
    'ExchangeFactory',
    'BinanceExchange',
    'PoloniexExchange'
]