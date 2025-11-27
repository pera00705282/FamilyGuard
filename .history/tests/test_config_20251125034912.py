"""Test configuration for WebSocket tests."""
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Mock the imports to avoid dependency issues
sys.modules['crypto_trading'] = MagicMock()
sys.modules['crypto_trading.exchanges'] = MagicMock()
sys.modules['crypto_trading.exchanges.websocket'] = MagicMock()

# Now import the actual implementation
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

# Mock the BinanceWebSocketClient class
class MockBinanceWebSocketClient(BinanceWebSocketClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ws = AsyncMock()
        self._ws.send = AsyncMock()
        self._ws.open = True
        self._connect = AsyncMock()
        self._callbacks = {}
    
    async def connect(self):
        self._connected.set()
    
    async def disconnect(self):
        self._connected.clear()
    
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
