"""



Example usage of the Binance exchange client.
"""

    ExchangeFactory,
    BinanceExchange,
    BinanceWebSocketClient
)

# Configuration
API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')
SYMBOL = 'BTCUSDT'

async def main():
    # Create exchange instance using factory
    exchange = ExchangeFactory.create_exchange(
        'binance',
        api_key=API_KEY,
        api_secret=API_SECRET
    )

    try:
        # Connect to the exchange
        await exchange.connect()
        print(f"Connected to {exchange.name}")

        # Get ticker
        ticker = await exchange.get_ticker(SYMBOL)
        print(f"{SYMBOL} Ticker:")
        print(f"  Last: {ticker.last}")
        print(f"  Bid: {ticker.bid}")
        print(f"  Ask: {ticker.ask}")

        # Get order book
        order_book = await exchange.get_order_book(SYMBOL)
        print(f"\nOrder Book for {SYMBOL}:")
        print("Top 5 Bids:")
        for price, amount in order_book.bids[:5]:
            print(f"  {price} - {amount}")
        print("Top 5 Asks:")
        for price, amount in order_book.asks[:5]:
            print(f"  {price} - {amount}")

        # Get balance if API key is provided
        if API_KEY and API_SECRET:
            print("\nAccount Balances:")
            balances = await exchange.get_balance()
            for asset, balance in balances.items():
                if balance > 0:
                    print(f"  {asset}: {balance}")

        # WebSocket example
        print("\nStarting WebSocket feed...")
        await websocket_example()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.disconnect()
        print("Disconnected from exchange")

async def websocket_example():
    """Example of using WebSocket client."""
    ws = BinanceWebSocketClient()

    # Define callbacks
    async def on_ticker_update(update):
        print(f"Ticker update: {update.symbol} - Last: {update.last}")

    async def on_order_book_update(update):
        print(f"Order book update: {update.symbol}")

    # Register callbacks
    ws.register_callback('ticker', on_ticker_update)
    ws.register_callback('order_book', on_order_book_update)

    # Connect and subscribe
    await ws.connect()
    await ws.subscribe(f"{SYMBOL.lower()}@ticker")
    await ws.subscribe(f"{SYMBOL.lower()}@depth@100ms")

    try:
        # Keep the connection alive for 30 seconds
        print("WebSocket connected. Press Ctrl+C to exit.")
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        print("\nClosing WebSocket...")
    finally:
        await ws.disconnect()

if __name__ == "__main__":
    asyncio.run(main())