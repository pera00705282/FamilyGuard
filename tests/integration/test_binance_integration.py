"""Integration tests for Binance WebSocket client with real API."""
import asyncio
import os
import pytest
from decimal import Decimal

from crypto_trading.exchanges.websocket.binance_websocket import BinanceWebSocketClient

# Skip these tests if running in CI environment without API keys
pytestmark = pytest.mark.skipif(
    not os.getenv('BINANCE_API_KEY') or not os.getenv('BINANCE_API_SECRET'),
    reason='Binance API keys not found in environment variables'
)

class TestBinanceIntegration:
    """Integration tests for Binance WebSocket client."""

    @pytest.fixture
    def binance_ws(self):
        """Create a BinanceWebSocketClient instance with API keys from environment."""
        return BinanceWebSocketClient(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET')
        )
    
    @pytest.mark.asyncio
    async def test_ticker_stream(self, binance_ws):
        """Test subscribing to ticker stream."""
        received_messages = []

        async def on_ticker(ticker):
            received_messages.append(ticker)
            if len(received_messages) >= 3:  # Get 3 updates before disconnecting
                await binance_ws.disconnect()

        try:
            # Connect and subscribe
            binance_ws.on_ticker(on_ticker)
            await binance_ws.connect()
            await binance_ws.subscribe('btcusdt@ticker')

            # Wait for messages with timeout
            await asyncio.wait_for(binance_ws._message_handler_task, timeout=10)

        except asyncio.TimeoutError:
            pass  # Expected when we disconnect

        finally:
            # Cleanup
            if binance_ws.is_connected():
                await binance_ws.disconnect()
        
        # Verify we received some messages
        assert len(received_messages) >= 1
        assert isinstance(received_messages[0].symbol, str)
        assert isinstance(received_messages[0].bid, Decimal)
        assert isinstance(received_messages[0].ask, Decimal)
    
    @pytest.mark.asyncio
    async def test_trade_stream(self, binance_ws):
        """Test subscribing to trade stream."""
        received_messages = []
        
        async def on_trade(trade):
            received_messages.append(trade)
            if len(received_messages) >= 3:  # Get 3 updates before disconnecting
                await binance_ws.disconnect()
        
        try:
            # Connect and subscribe
            binance_ws.on_trades(on_trade)
            await binance_ws.connect()
            await binance_ws.subscribe('btcusdt@trade')
            
            # Wait for messages with timeout
            await asyncio.wait_for(binance_ws._message_handler_task, timeout=10)
            
        except asyncio.TimeoutError:
            pass  # Expected when we disconnect
            
        finally:
            # Cleanup
            if binance_ws.is_connected():
                await binance_ws.disconnect()
        
        # Verify we received some messages
        assert len(received_messages) >= 1
        assert received_messages[0].symbol == 'BTCUSDT'
        assert isinstance(received_messages[0].price, Decimal)
        assert isinstance(received_messages[0].amount, Decimal)
        assert received_messages[0].side in ['buy', 'sell']
    
    @pytest.mark.asyncio
    async def test_orderbook_stream(self, binance_ws):
        """Test subscribing to order book stream."""
        received_messages = []
        
        async def on_orderbook(book):
            received_messages.append(book)
            if len(received_messages) >= 2:  # Get 2 updates before disconnecting
                await binance_ws.disconnect()
        
        try:
            # Connect and subscribe
            binance_ws.on_orderbook(on_orderbook)
            await binance_ws.connect()
            await binance_ws.subscribe('btcusdt@depth@100ms')
            
            # Wait for messages with timeout
            await asyncio.wait_for(binance_ws._message_handler_task, timeout=10)
            
        except asyncio.TimeoutError:
            pass  # Expected when we disconnect
            
        finally:
            # Cleanup
            if binance_ws.is_connected():
                await binance_ws.disconnect()
        
        # Verify we received some messages
        assert len(received_messages) >= 1
        assert received_messages[0].symbol == 'BTCUSDT'
        assert len(received_messages[0].bids) > 0
        assert len(received_messages[0].asks) > 0
        assert isinstance(received_messages[0].bids[0][0], Decimal)  # Price
        assert isinstance(received_messages[0].bids[0][1], Decimal)  # Amount

    @pytest.mark.asyncio
    async def test_multiple_streams(self, binance_ws):
        """Test subscribing to multiple streams in one connection."""
        ticker_received = False
        trade_received = False
        
        async def on_ticker(ticker):
            nonlocal ticker_received
            ticker_received = True
            if ticker_received and trade_received:
                await binance_ws.disconnect()
        
        async def on_trade(trade):
            nonlocal trade_received
            trade_received = True
            if ticker_received and trade_received:
                await binance_ws.disconnect()
        
        try:
            # Connect and subscribe to multiple streams
            binance_ws.on_ticker(on_ticker)
            binance_ws.on_trades(on_trade)
            await binance_ws.connect()
            await binance_ws.subscribe(['btcusdt@ticker', 'btcusdt@trade'])
            
            # Wait for messages with timeout
            await asyncio.wait_for(binance_ws._message_handler_task, timeout=15)
            
        except asyncio.TimeoutError:
            pass  # Expected when we disconnect
            
        finally:
            # Cleanup
            if binance_ws.is_connected():
                await binance_ws.disconnect()
        
        # Verify we received both types of messages
        assert ticker_received is True
        assert trade_received is True
