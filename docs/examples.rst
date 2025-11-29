Examples
========

This page contains practical examples of how to use the Crypto Trading library.

Basic Usage
-----------

Fetching Ticker Data
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    from crypto_trading.exchanges import ExchangeFactory

    async def main():
        # Initialize the exchange client
        exchange = ExchangeFactory.create('binance')
        
        # Get ticker data
        ticker = await exchange.get_ticker('BTC/USDT')
        print(f"BTC/USDT - Last: {ticker.last}, 24h Volume: {ticker.base_volume}")
        
        # Get order book
        order_book = await exchange.get_order_book('BTC/USDT', limit=5)
        print(f"Best bid: {order_book.best_bid()}")
        print(f"Best ask: {order_book.best_ask()}")
        
        # Get recent trades
        trades = await exchange.get_recent_trades('BTC/USDT', limit=3)
        for trade in trades:
            print(f"Trade: {trade.side} {trade.quantity} @ {trade.price}")

    if __name__ == "__main__":
        asyncio.run(main())

Placing Orders
~~~~~~~~~~~~~

.. code-block:: python

    from decimal import Decimal
    from crypto_trading.exchanges import ExchangeFactory, OrderSide, OrderType, TimeInForce

    async def place_orders():
        # Initialize with API credentials for trading
        exchange = ExchangeFactory.create(
            'binance',
            api_key='your-api-key',
            api_secret='your-api-secret',
            testnet=True  # Use testnet for development
        )
        
        try:
            # Place a limit buy order
            buy_order = await exchange.create_order(
                symbol='BTC/USDT',
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal('0.01'),
                price=Decimal('40000.00'),
                time_in_force=TimeInForce.GTC
            )
            print(f"Buy order placed: {buy_order.order_id}")

            # Place a market sell order
            sell_order = await exchange.create_order(
                symbol='BTC/USDT',
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=Decimal('0.01')
            )
            print(f"Market sell order executed: {sell_order.order_id}")

        except Exception as e:
            print(f"Error placing order: {e}")

WebSocket Example
----------------

Real-time Price Updates
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import asyncio
    from crypto_trading.exchanges.websocket import BinanceWebSocketClient

    async def on_ticker(ticker):
        print(f"Ticker update - {ticker.symbol}: {ticker.last}")

    async def on_order_book(book):
        print(f"Order book update - {book.symbol}")
        print(f"Best bid: {book.best_bid()}")
        print(f"Best ask: {book.best_ask()}")

    async def main():
        ws = BinanceWebSocketClient()
        
        # Register callbacks
        ws.on_ticker(on_ticker)
        ws.on_order_book(on_order_book)
        
        # Connect and subscribe
        await ws.connect()
        await ws.subscribe_ticker('btcusdt')
        await ws.subscribe_order_book('btcusdt')
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)

    if __name__ == "__main__":
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Disconnecting...")
            asyncio.run(ws.disconnect())

Order Management
---------------

Checking Order Status
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    async def check_orders():
        exchange = ExchangeFactory.create('binance', api_key='...', api_secret='...')
        
        # Get a specific order
        try:
            order = await exchange.get_order('12345', 'BTC/USDT')
            print(f"Order status: {order.status}")
            print(f"Filled: {order.filled_quantity}/{order.quantity}")
        except OrderNotFound:
            print("Order not found")
        
        # Get all open orders
        open_orders = await exchange.get_open_orders('BTC/USDT')
        print(f"Open orders: {len(open_orders)}")
        
        # Cancel an order
        if open_orders:
            order_id = open_orders[0].order_id
            canceled = await exchange.cancel_order(order_id, 'BTC/USDT')
            if canceled:
                print(f"Canceled order: {order_id}")

Account Management
-----------------

Checking Balances
~~~~~~~~~~~~~~~~

.. code-block:: python

    async def check_balance():
        exchange = ExchangeFactory.create('binance', api_key='...', api_secret='...')
        
        # Get all balances
        balances = await exchange.get_balance()
        
        # Print non-zero balances
        for asset, balance in balances.items():
            if balance['total'] > 0:
                print(f"{asset}: {balance['free']} free, {balance['used']} in orders")
        
        # Get specific asset balance
        btc_balance = balances.get('BTC', {}).get('free', Decimal('0'))
        print(f"Available BTC: {btc_balance}")

Error Handling
-------------

Basic Error Handling
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from crypto_trading.exchanges import (
        ExchangeError,
        RateLimitExceeded,
        InsufficientFunds,
        InvalidOrder
    )

    async def safe_trade():
        exchange = ExchangeFactory.create('binance', api_key='...', api_secret='...')
        
        try:
            await exchange.create_order(
                symbol='BTC/USDT',
                side='buy',
                order_type='limit',
                quantity=Decimal('1000'),  # Intentionally high to trigger error
                price=Decimal('1.00')
            )
        except InsufficientFunds as e:
            print(f"Not enough funds. Available: {e.available}, Required: {e.required}")
        except RateLimitExceeded as e:
            print(f"Rate limited. Retry after {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
        except InvalidOrder as e:
            print(f"Invalid order: {e.reason}")
        except ExchangeError as e:
            print(f"Exchange error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
