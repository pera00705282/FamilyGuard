"""Tests for Binance WebSocket client."""
import asyncio
import json
import logging
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crypto_trading.exchanges.websocket.binance_websocket import BinanceWebSocketClient
from crypto_trading.exchanges.base.websocket import TickerUpdate, OrderBookUpdate

# Configure logger for tests
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(handler)

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
    async def test_parse_message(self, binance_ws):
        """Test message parsing."""
        # Test string message
        message = '{"e":"24hrTicker","s":"BTCUSDT"}'
        result = binance_ws._parse_message(message)
        assert result == {"e": "24hrTicker", "s": "BTCUSDT"}

        # Test bytes message
        message_bytes = b'{"e":"24hrTicker","s":"BTCUSDT"}'
        result = binance_ws._parse_message(message_bytes)
        assert result == {"e": "24hrTicker", "s": "BTCUSDT"}

        # Test invalid JSON
        with pytest.raises(json.JSONDecodeError):
            binance_ws._parse_message('invalid json')

    @pytest.mark.asyncio
    async def test_handle_combined_stream(self, binance_ws):
        """Test handling of combined stream messages."""
        binance_ws._handle_ticker = AsyncMock()
        binance_ws._handle_orderbook = AsyncMock()
        binance_ws._handle_trade = AsyncMock()
        binance_ws._handle_kline = AsyncMock()
        
        # Test ticker stream
        data = {
            'stream': 'btcusdt@ticker',
            'data': SAMPLE_TICKER
        }
        await binance_ws._handle_combined_stream(data)
        binance_ws._handle_ticker.assert_awaited_once_with('btcusdt', SAMPLE_TICKER)

        # Test depth stream
        binance_ws._handle_ticker.reset_mock()
        data = {
            'stream': 'btcusdt@depth',
            'data': SAMPLE_DEPTH_UPDATE
        }
        await binance_ws._handle_combined_stream(data)
        binance_ws._handle_orderbook.assert_awaited_once_with('btcusdt', SAMPLE_DEPTH_UPDATE)

        # Test trade stream
        binance_ws._handle_orderbook.reset_mock()
        data = {
            'stream': 'btcusdt@trade',
            'data': SAMPLE_TRADE
        }
        await binance_ws._handle_combined_stream(data)
        binance_ws._handle_trade.assert_awaited_once_with('btcusdt', SAMPLE_TRADE)
        
        # Test unknown stream type
        binance_ws._handle_trade.reset_mock()
        data = {
            'stream': 'btcusdt@unknown',
            'data': {}
        }
        with patch.object(logger, 'debug') as mock_debug:
            await binance_ws._handle_combined_stream(data)
            mock_debug.assert_called_once_with(
                'Unhandled stream type: btcusdt@unknown'
            )

    @pytest.mark.asyncio
    async def test_handle_standard_event(self, binance_ws):
        """Test handling of standard event messages."""
        binance_ws._handle_ticker = AsyncMock()
        binance_ws._handle_orderbook = AsyncMock()
        binance_ws._handle_trade = AsyncMock()
        binance_ws._handle_kline = AsyncMock()
        binance_ws._handle_execution_report = AsyncMock()
        binance_ws._handle_balance_update = AsyncMock()
        
        # Test ticker event
        data = {'e': '24hrTicker', 's': 'BTCUSDT'}
        await binance_ws._handle_standard_event(data)
        binance_ws._handle_ticker.assert_awaited_once_with('btcusdt', data)

        # Test depth update event
        binance_ws._handle_ticker.reset_mock()
        data = {'e': 'depthUpdate', 's': 'BTCUSDT'}
        await binance_ws._handle_standard_event(data)
        binance_ws._handle_orderbook.assert_awaited_once_with('btcusdt', data)

        # Test trade event
        binance_ws._handle_orderbook.reset_mock()
        data = {'e': 'trade', 's': 'BTCUSDT'}
        await binance_ws._handle_standard_event(data)
        binance_ws._handle_trade.assert_awaited_once_with('btcusdt', data)
        
        # Test execution report
        binance_ws._handle_trade.reset_mock()
        data = {'e': 'executionReport', 's': 'BTCUSDT'}
        await binance_ws._handle_standard_event(data)
        binance_ws._handle_execution_report.assert_awaited_once_with(data)

        # Test unknown event type
        binance_ws._handle_execution_report.reset_mock()
        data = {'e': 'unknownEvent', 's': 'BTCUSDT'}
        with patch.object(logger, 'debug') as mock_debug:
            await binance_ws._handle_standard_event(data)
            mock_debug.assert_called_once_with(
                'Unhandled event type: unknownEvent'
            )

    @pytest.mark.asyncio
    async def test_handle_message(self, binance_ws):
        """Test the main message handler with different message types."""
        # Mock internal methods
        binance_ws._parse_message = MagicMock()
        binance_ws._handle_combined_stream = AsyncMock()
        binance_ws._handle_standard_event = AsyncMock()
        
        # Test combined stream message
        combined_data = {'stream': 'btcusdt@ticker', 'data': SAMPLE_TICKER}
        binance_ws._parse_message.return_value = combined_data

        await binance_ws._handle_message('dummy message')
        binance_ws._handle_combined_stream.assert_awaited_once_with(combined_data)

        # Test standard event message
        binance_ws._handle_combined_stream.reset_mock()
        event_data = {'e': '24hrTicker', 's': 'BTCUSDT'}
        binance_ws._parse_message.return_value = event_data

        await binance_ws._handle_message('dummy message')
        binance_ws._handle_standard_event.assert_awaited_once_with(event_data)
        
        # Test subscription confirmation
        binance_ws._handle_standard_event.reset_mock()
        sub_data = {'result': None, 'id': 123}
        binance_ws._parse_message.return_value = sub_data

        with patch.object(logger, 'debug') as mock_debug:
            await binance_ws._handle_message('dummy message')
            mock_debug.assert_called_once_with(
                f'Subscription confirmed: {sub_data}'
            )
        
        # Test error message
        error_data = {'error': {'code': -1234, 'msg': 'Invalid request'}}
        binance_ws._parse_message.return_value = error_data

        with patch.object(logger, 'error') as mock_error:
            await binance_ws._handle_message('dummy message')
            mock_error.assert_called_once_with(
                "WebSocket error: {'code': -1234, 'msg': 'Invalid request'}"
            )
        
        # Test JSON decode error
        binance_ws._parse_message.side_effect = json.JSONDecodeError(
            "Expecting value", "", 0
        )
        with patch.object(logger, 'error') as mock_error:
            await binance_ws._handle_message('invalid json')
            mock_error.assert_called_once()
            assert 'Failed to parse WebSocket message' in mock_error.call_args[0][0]
        
        # Test other exceptions
        binance_ws._parse_message.side_effect = Exception('Test error')
        with patch.object(logger, 'error') as mock_error:
            await binance_ws._handle_message('dummy message')
            mock_error.assert_called_once()
            assert 'Error processing WebSocket message' in mock_error.call_args[0][0]
    
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
