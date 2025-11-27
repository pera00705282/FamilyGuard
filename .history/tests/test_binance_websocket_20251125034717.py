"""
Tests for Binance WebSocket client.
"""
import asyncio
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from websockets.exceptions import ConnectionClosed

from crypto_trading.exchanges.websocket.binance_websocket import BinanceWebSocketClient
from crypto_trading.exchanges.base.websocket import TickerUpdate, OrderBookUpdate, Trade

# Test data
SAMPLE_TICKER = {
    "e": "24hrTicker",
    "E": 123456789,
    "s": "BTCUSDT",
    "p": "100.00",
    "P": "1.50",
    "w": "9000.00",
    "x": "8000.00",
    "c": "8100.00",
    "Q": "0.1",
    "b": "8099.00",
    "B": "1.0",
    "a": "8101.00",
    "A": "1.5",
    "o": "8000.00",
    "h": "8200.00",
    "l": "7950.00",
    "v": "1000.00",
    "q": "8000000.00",
    "O": 0,
    "C": 0,
    "F": 0,
    "L": 0,
    "n": 0
}

SAMPLE_DEPTH_UPDATE = {
    "e": "depthUpdate",
    "E": 123456789,
    "s": "BTCUSDT",
    "U": 1,
    "u": 2,
    "b": [
        ["8000.00", "1.0"],
        ["7999.50", "2.0"]
    ],
    "a": [
        ["8001.00", "1.5"],
        ["8001.50", "0.5"]
    ]
}

SAMPLE_TRADE = {
    "e": "trade",
    "E": 123456789,
    "s": "BTCUSDT",
    "t": 12345,
    "p": "8100.00",
    "q": "0.1",
    "b": 88,
    "a": 50,
    "T": 123456789,
    "m": True,
    "M": True
}

SAMPLE_COMBINED_STREAM = {
    "stream": "btcusdt@ticker/ethusdt@ticker",
    "data": {
        "e": "24hrTicker",
        "E": 123456789,
        "s": "BTCUSDT",
        "p": "100.00",
        "P": "1.50",
        "w": "9000.00",
        "x": "8000.00",
        "c": "8100.00",
        "Q": "0.1",
        "b": "8099.00",
        "B": "1.0",
        "a": "8101.00",
        "A": "1.5",
        "o": "8000.00",
        "h": "8200.00",
        "l": "7950.00",
        "v": "1000.00",
        "q": "8000000.00"
    }
}

SAMPLE_AGG_TRADE = {
    "e": "aggTrade",
    "E": 123456789,
    "s": "BTCUSDT",
    "a": 12345,
    "p": "8100.00",
    "q": "0.1",
    "f": 100,
    "l": 105,
    "T": 123456789,
    "m": True,
    "M": True
}

SAMPLE_ORDER_UPDATE = {
    "e": "executionReport",
    "E": 123456789,
    "s": "BTCUSDT",
    "c": "mymostimportantclientorder",
    "S": "BUY",
    "o": "LIMIT",
    "f": "GTC",
    "q": "1.00000000",
    "p": "0.10259210",
    "P": "0.00000000",
    "F": "0.00000000",
    "g": -1,
    "C": "canceled",
    "x": "NEW",
    "X": "NEW",
    "r": "NONE",
    "i": 1,
    "l": "0.00000000",
    "z": "0.00000000",
    "L": "0.00000000",
    "n": "0",
    "N": None,
    "T": 123456789,
    "t": -1,
    "I": 1,
    "w": True,
    "m": False,
    "M": False,
    "O": 123456789,
    "Z": "0.00000000",
    "Y": "0.00000000",
    "Q": "0.00000000"
}

@pytest.fixture
def binance_ws():
    """Fixture that provides a BinanceWebSocketClient instance."""
    with patch('websockets.connect', new_callable=AsyncMock) as mock_ws:
        mock_ws.return_value.__aenter__.return_value = AsyncMock()
        client = BinanceWebSocketClient()
        # Setup mock for _connect method
        client._connect = AsyncMock()
        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client._ws.open = True
        yield client

class TestBinanceWebSocket:
    """Test cases for BinanceWebSocketClient."""
    
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, binance_ws):
        """Test WebSocket connection and disconnection."""
        # Mock the websockets.connect function
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_ws
            
            # Test connection
            await binance_ws.connect()
            assert binance_ws.is_connected() is True
            mock_connect.assert_called_once()
            
            # Test disconnection
            await binance_ws.disconnect()
            assert binance_ws.is_connected() is False
            mock_ws.close.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_subscribe(self, binance_ws, mock_websocket):
        """Test subscribing to channels."""
        binance_ws._ws = mock_websocket
        binance_ws._ws.send = AsyncMock()
        
        # Test single channel subscription
        await binance_ws.subscribe('btcusdt@ticker')
        binance_ws._ws.send.assert_awaited_once_with(json.dumps({
            "method": "SUBSCRIBE",
            "params": ["btcusdt@ticker"],
            "id": 1
        }))
        
        # Test multiple channels
        binance_ws._ws.send.reset_mock()
        await binance_ws.subscribe(['btcusdt@depth@100ms', 'btcusdt@trade'])
        binance_ws._ws.send.assert_awaited_once_with(json.dumps({
            "method": "SUBSCRIBE",
            "params": ["btcusdt@depth@100ms", "btcusdt@trade"],
            "id": 1
        }))
    
    @pytest.mark.asyncio
    async def test_process_ticker_message(self, binance_ws):
        """Test processing ticker messages."""
        callback = AsyncMock()
        binance_ws.register_callback('ticker', callback)
        
        # Process ticker message
        await binance_ws._process_message(SAMPLE_TICKER)
        
        # Verify callback was called with correct data
        callback.assert_awaited_once()
        args = callback.await_args[0][0]
        assert isinstance(args, TickerUpdate)
        assert args.symbol == 'BTCUSDT'
        assert args.last == 8100.00
        assert args.bid == 8099.00
        assert args.ask == 8101.00
    
    @pytest.mark.asyncio
    async def test_process_depth_update(self, binance_ws):
        """Test processing order book updates."""
        callback = AsyncMock()
        binance_ws.register_callback('order_book', callback)
        
        # Process depth update
        await binance_ws._process_message(SAMPLE_DEPTH_UPDATE)
        
        # Verify callback was called with correct data
        callback.assert_awaited_once()
        args = callback.await_args[0][0]
        assert isinstance(args, OrderBookUpdate)
        assert args.symbol == 'BTCUSDT'
        assert len(args.bids) == 2
        assert len(args.asks) == 2
        assert args.bids[0] == (Decimal('8000.00'), Decimal('1.0'))
    
    @pytest.mark.asyncio
    async def test_reconnect_on_error(self, binance_ws):
        """Test reconnection on connection error."""
        with patch.object(binance_ws, '_connect', new_callable=AsyncMock) as mock_connect:
            # Simulate connection error
            mock_connect.side_effect = [ConnectionError(), None]
            
            # This should trigger a reconnection
            await binance_ws.connect()
            
            # Should have tried to connect twice
            assert mock_connect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_consumer_task(self, binance_ws, event_loop):
        """Test the WebSocket consumer task."""
        # Set up mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            json.dumps(SAMPLE_TICKER),
            json.dumps(SAMPLE_DEPTH_UPDATE),
            asyncio.CancelledError()  # To stop the loop
        ]
        binance_ws._ws = mock_ws
        
        # Set up callbacks
        ticker_callback = AsyncMock()
        orderbook_callback = AsyncMock()
        binance_ws.register_callback('ticker', ticker_callback)
        binance_ws.register_callback('order_book', orderbook_callback)
        
        # Run the consumer task
        with pytest.raises(asyncio.CancelledError):
            await binance_ws._consumer()
        
        # Verify callbacks were called
        ticker_callback.assert_awaited_once()
        orderbook_callback.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_invalid_message(self, binance_ws, caplog):
        """Test handling of invalid messages."""
        # Invalid JSON
        binance_ws._ws = AsyncMock()
        binance_ws._ws.recv.return_value = "{invalid json"
        
        await binance_ws._process_raw_message("{invalid json")
        assert "Error parsing message" in caplog.text
        
        # Unknown message type
        caplog.clear()
        await binance_ws._process_message({"e": "unknown_event"})
        assert "Unknown message type" in caplog.text
