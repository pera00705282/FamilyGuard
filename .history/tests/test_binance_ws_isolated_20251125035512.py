"""
Isolated tests for Binance WebSocket client.
These tests don't depend on other parts of the system.
"""
import asyncio
import json
import logging
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock, call
import pytest
from decimal import Decimal

# Configure test logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock the imports to avoid dependency issues
class TickerUpdate:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.symbol = kwargs.get('symbol')
        self.last = Decimal(kwargs.get('last', '0'))
        self.timestamp = kwargs.get('timestamp', int(datetime.now().timestamp() * 1000))

class OrderBookUpdate:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.symbol = kwargs.get('symbol')
        self.bids = kwargs.get('bids', [])
        self.asks = kwargs.get('asks', [])
        self.timestamp = kwargs.get('timestamp', int(datetime.now().timestamp() * 1000))

class Trade:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.symbol = kwargs.get('symbol')
        self.price = Decimal(kwargs.get('price', '0'))
        self.quantity = Decimal(kwargs.get('quantity', '0'))
        self.is_buyer_maker = kwargs.get('is_buyer_maker', False)
        self.timestamp = kwargs.get('timestamp', int(datetime.now().timestamp() * 1000))

# Mock the BaseWebSocketClient
class BaseWebSocketClient:
    def __init__(self, url, api_key=None, api_secret=None):
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self._callbacks = {}
        self._connected = asyncio.Event()
        self._ws = None
        self._subscriptions = set()
    
    def register_callback(self, event_type, callback):
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    async def _run_callback(self, callback, *args, **kwargs):
        if asyncio.iscoroutinefunction(callback):
            await callback(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, callback, *args, **kwargs)

# Import the actual implementation
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from src.crypto_trading.exchanges.websocket.binance_websocket import BinanceWebSocketClient

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
    "q": "8000000.00"
}

SAMPLE_ORDER_BOOK = {
    "e": "depthUpdate",
    "E": 123456789,
    "s": "BTCUSDT",
    "U": 1,
    "u": 2,
    "b": [["8000.00", "1.0"], ["7999.50", "2.5"]],
    "a": [["8100.00", "0.5"], ["8101.00", "1.5"]]
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
    "stream": "btcusdt@ticker",
    "data": SAMPLE_TICKER
}

SAMPLE_ORDER_UPDATE = {
    "e": "executionReport",
    "E": 1499405658658,
    "s": "BTCUSDT",
    "c": "mUvoqJxFIILMdfAW5iGSOW",
    "S": "BUY",
    "o": "LIMIT",
    "f": "GTC",
    "q": "0.001",
    "p": "0.0",
    "P": "0.0",
    "F": "0.0",
    "g": -1,
    "C": "canceled",
    "x": "NEW",
    "X": "NEW",
    "r": "NONE",
    "i": 1,
    "l": "0.0",
    "z": "0.0",
    "L": "0.0",
    "n": "0",
    "N": None,
    "T": 1499405658657,
    "t": -1,
    "I": 1,
    "w": True,
    "m": False,
    "M": False,
    "O": 1499405658657,
    "Z": "0.0",
    "Y": "0.0"
}

@pytest.fixture
def binance_ws():
    """Create a BinanceWebSocketClient with mocked WebSocket."""
    with patch('websockets.connect', new_callable=AsyncMock) as mock_ws:
        mock_ws.return_value.__aenter__.return_value = AsyncMock()
        client = BinanceWebSocketClient()
        client._connect = AsyncMock()
        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client._ws.open = True
        client._ws.recv = AsyncMock()
        client._connected.set()
        yield client

@pytest.mark.asyncio
async def test_initialization():
    """Test WebSocket client initialization."""
    client = BinanceWebSocketClient()
    assert client.url == "wss://stream.binance.com:9443/ws"
    assert client._callbacks == {}
    assert not client._connected.is_set()

@pytest.mark.asyncio
async def test_connect(binance_ws):
    """Test WebSocket connection."""
    await binance_ws.connect()
    binance_ws._connect.assert_called_once()
    assert binance_ws._connected.is_set()

@pytest.mark.asyncio
async def test_subscribe_single_channel(binance_ws):
    """Test subscribing to a single channel."""
    await binance_ws.subscribe('btcusdt@ticker')
    
    # Verify the subscription message
    binance_ws._ws.send.assert_called_once()
    call_args = binance_ws._ws.send.call_args[0][0]
    payload = json.loads(call_args)
    
    assert payload['method'] == 'SUBSCRIBE'
    assert 'btcusdt@ticker' in payload['params']
    assert binance_ws.url == "wss://stream.binance.com:9443/ws"

@pytest.mark.asyncio
async def test_subscribe_multiple_channels(binance_ws):
    """Test subscribing to multiple channels with combined streams."""
    channels = ['btcusdt@ticker', 'ethusdt@ticker']
    await binance_ws.subscribe(channels)
    
    # Should use combined streams URL
    assert "wss://stream.binance.com:9443/stream?streams=" in binance_ws.url
    assert 'btcusdt@ticker' in binance_ws.url
    assert 'ethusdt@ticker' in binance_ws.url
    
    # Should send subscription message for each channel
    assert binance_ws._ws.send.call_count == 1
    call_args = binance_ws._ws.send.call_args[0][0]
    payload = json.loads(call_args)
    assert payload['method'] == 'SUBSCRIBE'
    assert len(payload['params']) == 2
    assert set(payload['params']) == set(channels)

@pytest.mark.asyncio
async def test_unsubscribe(binance_ws):
    """Test unsubscribing from channels."""
    channels = ['btcusdt@ticker', 'ethusdt@ticker']
    await binance_ws.subscribe(channels)
    
    # Reset mock to track unsubscribe calls
    binance_ws._ws.send.reset_mock()
    
    # Unsubscribe from one channel
    await binance_ws.unsubscribe(['btcusdt@ticker'])
    
    # Verify unsubscribe message
    binance_ws._ws.send.assert_called_once()
    call_args = binance_ws._ws.send.call_args[0][0]
    payload = json.loads(call_args)
    
    assert payload['method'] == 'UNSUBSCRIBE'
    assert 'btcusdt@ticker' in payload['params']
    assert 'ethusdt@ticker' not in payload['params']

@pytest.mark.asyncio
async def test_handle_combined_stream(binance_ws):
    """Test handling of combined stream messages."""
    # Setup mock callbacks
    ticker_callback = AsyncMock()
    binance_ws.register_callback('ticker', ticker_callback)
    
    # Simulate receiving a combined stream message
    message = json.dumps(SAMPLE_COMBINED_STREAM)
    await binance_ws._handle_message(message)
    
    # Check that the callback was called with the right data
    assert ticker_callback.called
    ticker = ticker_callback.call_args[0][0]
    assert ticker.symbol == 'BTCUSDT'
    assert ticker.last == Decimal('8100.00')

@pytest.mark.asyncio
async def test_handle_order_book_update(binance_ws):
    """Test handling of order book update messages."""
    # Setup mock callback
    order_book_callback = AsyncMock()
    binance_ws.register_callback('order_book', order_book_callback)
    
    # Simulate receiving an order book update
    message = json.dumps(SAMPLE_ORDER_BOOK)
    await binance_ws._handle_message(message)
    
    # Check that the callback was called with the right data
    assert order_book_callback.called
    update = order_book_callback.call_args[0][0]
    assert update.symbol == 'BTCUSDT'
    assert len(update.bids) == 2
    assert len(update.asks) == 2
    assert update.bids[0][0] == Decimal('8000.00')
    assert update.bids[0][1] == Decimal('1.0')

@pytest.mark.asyncio
async def test_handle_trade(binance_ws):
    """Test handling of trade messages."""
    # Setup mock callback
    trade_callback = AsyncMock()
    binance_ws.register_callback('trade', trade_callback)
    
    # Simulate receiving a trade message
    message = json.dumps(SAMPLE_TRADE)
    await binance_ws._handle_message(message)
    
    # Check that the callback was called with the right data
    assert trade_callback.called
    trade = trade_callback.call_args[0][0]
    assert trade.symbol == 'BTCUSDT'
    assert trade.price == Decimal('8100.00')
    assert trade.quantity == Decimal('0.1')
    assert trade.is_buyer_maker is True

@pytest.mark.asyncio
async def test_handle_order_update(binance_ws):
    """Test handling of order update messages."""
    # Setup mock callback
    order_callback = AsyncMock()
    binance_ws.register_callback('order_update', order_callback)
    
    # Simulate receiving an order update
    message = json.dumps(SAMPLE_ORDER_UPDATE)
    await binance_ws._handle_message(message)
    
    # Check that the callback was called with the right data
    assert order_callback.called
    order = order_callback.call_args[0][0]
    assert order.symbol == 'BTCUSDT'
    assert order.side == 'BUY'
    assert order.order_type == 'LIMIT'

@pytest.mark.asyncio
async def test_handle_unknown_message(binance_ws, caplog):
    """Test handling of unknown message types."""
    # Setup mock callback
    unknown_callback = AsyncMock()
    binance_ws.register_callback('unknown', unknown_callback)
    
    # Simulate receiving an unknown message type
    message = json.dumps({"e": "unknown_event", "data": "test"})
    await binance_ws._handle_message(message)
    
    # Check that no callback was called and a warning was logged
    assert not unknown_callback.called
    assert "Unknown message type: unknown_event" in caplog.text

@pytest.mark.asyncio
async def test_handle_invalid_json(binance_ws, caplog):
    """Test handling of invalid JSON messages."""
    # Simulate receiving invalid JSON
    await binance_ws._handle_message("not a json")
    
    # Check that an error was logged
    assert "Error parsing message" in caplog.text

@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test handling of connection errors."""
    with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
        # Make connect raise an exception
        mock_connect.side_effect = ConnectionError("Connection failed")
        client = BinanceWebSocketClient()
        
        with pytest.raises(ConnectionError):
            await client.connect()
        
        assert not client._connected.is_set()

@pytest.mark.asyncio
async def test_reconnect_logic():
    """Test automatic reconnection logic."""
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
         patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
        
        # First connection fails, second succeeds
        mock_connect.side_effect = [
            ConnectionError("First attempt failed"),
            AsyncMock()
        ]
        
        client = BinanceWebSocketClient(reconnect_attempts=2, reconnect_delay=0.1)
        
        # This should not raise an exception because of the retry
        await client.connect()
        
        # Check that sleep was called between retries
        mock_sleep.assert_called_once_with(0.1)
        assert mock_connect.call_count == 2

@pytest.mark.asyncio
async def test_message_processing(binance_ws):
    """Test the message processing loop."""
    # Setup mock callbacks
    ticker_callback = AsyncMock()
    binance_ws.register_callback('ticker', ticker_callback)
    
    # Simulate receiving messages
    binance_ws._ws.recv.side_effect = [
        json.dumps(SAMPLE_COMBINED_STREAM),
        asyncio.CancelledError()  # This will stop the loop
    ]
    
    # Run the message processing loop
    with pytest.raises(asyncio.CancelledError):
        await binance_ws._process_messages()
    
    # Check that the callback was called with the right data
    assert ticker_callback.called
    ticker = ticker_callback.call_args[0][0]
    assert ticker.symbol == 'BTCUSDT'
