API Reference
============

This document provides detailed information about the Crypto Trading API.

Exchange Clients
---------------

.. automodule:: crypto_trading.exchanges
   :members:
   :undoc-members:
   :show-inheritance:
   :member-order: bysource

Base Exchange Client
-------------------

.. autoclass:: crypto_trading.exchanges.interfaces.BaseExchangeClient
   :members:
   :undoc-members:
   :show-inheritance:
   :member-order: bysource

WebSocket Client
---------------

.. autoclass:: crypto_trading.exchanges.websocket.base_websocket.BaseWebSocketClient
   :members:
   :undoc-members:
   :show-inheritance:
   :member-order: bysource

Data Models
-----------

.. autoclass:: crypto_trading.exchanges.interfaces.TickerData
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: crypto_trading.exchanges.interfaces.OrderBookData
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: crypto_trading.exchanges.interfaces.TradeData
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: crypto_trading.exchanges.interfaces.OrderInfo
   :members:
   :undoc-members:
   :show-inheritance:

Enums
-----

.. automodule:: crypto_trading.exchanges.interfaces
   :members: OrderType, OrderSide, TimeInForce
   :undoc-members:
   :show-inheritance:

Exceptions
----------

.. autoexception:: crypto_trading.exchanges.interfaces.ExchangeError
   :members:
   :undoc-members:

.. autoexception:: crypto_trading.exchanges.interfaces.ExchangeNotAvailable
   :members:
   :undoc-members:

.. autoexception:: crypto_trading.exchanges.interfaces.RateLimitExceeded
   :members:
   :undoc-members:

.. autoexception:: crypto_trading.exchanges.interfaces.AuthenticationError
   :members:
   :undoc-members:

.. autoexception:: crypto_trading.exchanges.interfaces.InsufficientFunds
   :members:
   :undoc-members:

.. autoexception:: crypto_trading.exchanges.interfaces.InvalidOrder
   :members:
   :undoc-members:

.. autoexception:: crypto_trading.exchanges.interfaces.OrderNotFound
   :members:
   :undoc-members:
