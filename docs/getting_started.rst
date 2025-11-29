Getting Started
==============

This guide will help you get started with the Crypto Trading library.

Installation
------------

You can install the package using pip:

.. code-block:: bash

    pip install crypto-trading

Or install directly from source:

.. code-block:: bash

    git clone https://github.com/yourusername/crypto-trading.git
    cd crypto-trading
    pip install -e .

Basic Usage
-----------

Here's a quick example to get you started:

.. code-block:: python

    from crypto_trading.exchanges import ExchangeFactory
    import asyncio

    async def main():
        # Initialize the exchange client
        exchange = ExchangeFactory.create('binance', api_key='your-api-key', api_secret='your-api-secret')
        
        # Get ticker data
        ticker = await exchange.get_ticker('BTC/USDT')
        print(f"Current BTC/USDT price: {ticker.last}")

    if __name__ == "__main__":
        asyncio.run(main())

Configuration
-------------

The library can be configured using environment variables or directly in code:

.. code-block:: python

    from crypto_trading.config import settings
    
    # Configure settings
    settings.update({
        'log_level': 'INFO',
        'timeout': 30,
        'retry_attempts': 3
    })

Available Exchanges
-------------------

Currently supported exchanges:

- Binance (REST & WebSocket)
- More exchanges coming soon...

Authentication
--------------

To use authenticated endpoints, you'll need to provide API credentials:

.. code-block:: python

    exchange = ExchangeFactory.create(
        'binance',
        api_key='your-api-key',
        api_secret='your-api-secret',
        testnet=True  # Optional: use testnet for development
    )

Next Steps
----------

- Learn how to :doc:`use the API <api_reference>`
- Check out the :doc:`examples`
- Read the :doc:`contributing` guide
