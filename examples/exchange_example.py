"""
Example script demonstrating how to use the exchange connector.

This script shows how to:
1. Connect to an exchange
2. Get account balance
3. Get ticker data
4. Get order book data
5. Get available markets
6. Handle errors
"""

import asyncio
import logging
import os

from crypto_trading.exchanges import ExchangeFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to demonstrate exchange functionality."""
    # Initialize the exchange (default is Binance)
    exchange_name = os.getenv('EXCHANGE', 'binance')
    api_key = os.getenv('API_KEY', '')
    api_secret = os.getenv('API_SECRET', '')

    try:
        # Create exchange instance
        exchange = ExchangeFactory.create_exchange(
            exchange_name,
            api_key=api_key,
            api_secret=api_secret
        )

        # Connect to the exchange
        logger.info(f"Connecting to {exchange_name}...")
        await exchange.connect()
        logger.info("Connected successfully!")

        # Get account balance if API keys are provided
        if api_key and api_secret:
            logger.info("Fetching account balance...")
            balance = await exchange.get_balance()
            logger.info(f"Account balance: {balance}")

        # Get ticker for a trading pair (e.g., BTC/USDT)
        symbol = 'BTC/USDT'
        logger.info(f"Fetching ticker for {symbol}...")
        ticker = await exchange.get_ticker(symbol)
        logger.info(f"{symbol} Ticker:")
        logger.info(f"  Bid: {ticker.bid}")
        logger.info(f"  Ask: {ticker.ask}")
        logger.info(f"  Last: {ticker.last}")

        # Get order book
        logger.info(f"Fetching order book for {symbol}...")
        order_book = await exchange.get_order_book(symbol, limit=5)
        logger.info(f"Top 5 bids for {symbol}:")
        for price, amount in order_book.bids[:5]:
            logger.info(f"  {price} - {amount}")

        logger.info(f"Top 5 asks for {symbol}:")
        for price, amount in order_book.asks[:5]:
            logger.info(f"  {price} - {amount}")

        # Get available markets
        logger.info("Fetching available markets...")
        markets = await exchange.get_markets()
        logger.info(f"Found {len(markets)} markets")

        # Show first 5 markets as example
        for i, market in enumerate(markets[:5], 1):
            logger.info(f"  {i}. {market['base']}/{market['quote']}")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
    finally:
        # Disconnect from the exchange
        if 'exchange' in locals() and exchange is not None:
            await exchange.disconnect()
            logger.info("Disconnected from exchange")


if __name__ == "__main__":
    asyncio.run(main())