"""
Isolated tests for Binance WebSocket client.
These tests don't depend on other parts of the system.
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from decimal import Decimal

# Mock the imports to avoid dependency issues
class TickerUpdate:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class OrderBookUpdate:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class Trade:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

# Mock the BaseWebSocketClient
class BaseWebSocketClient:
    def __init__(self, url, api_key=None, api_secret=None):
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self._callbacks = {}
        self._connected = asyncio.Event()
        self._ws = None
    
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

# Now import the actual implementation
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

SAMPLE_COMBINED_STREAM = {
    "stream": "btcusdt@ticker",
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
        yield client

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

@pytest.mark.asyncio
async def test_handle_combined_stream(binance_ws):
    """Test handling of combined stream messages."""
    # Setup mock callback
    mock_callback = AsyncMock()
    binance_ws.register_callback('ticker', mock_callback)
    
    # Simulate receiving a combined stream message
    message = json.dumps(SAMPLE_COMBINED_STREAM)
    await binance_ws._handle_message(message)
    
    # Check that the callback was called with the right data
    assert mock_callback.called
    ticker = mock_callback.call_args[0][0]
    assert ticker.symbol == 'BTCUSDT'
    assert ticker.last == Decimal('8100.00')
