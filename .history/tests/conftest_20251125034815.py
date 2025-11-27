"""
Pytest configuration and fixtures for WebSocket testing.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from crypto_trading.exchanges.websocket import BinanceWebSocketClient

@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket client."""
    ws = MagicMock()
    ws.recv = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.__aenter__.return_value = ws
    return ws

@pytest.fixture
def binance_ws(mock_websocket):
    """Create a BinanceWebSocketClient with a mock WebSocket."""
    client = BinanceWebSocketClient()
    client._ws = mock_websocket
    return client

class MockWebSocketServer:
    """Mock WebSocket server for testing."""
    
    def __init__(self):
        self.messages = asyncio.Queue()
        self.connections = []
    
    async def handler(self, websocket, path):
        """Handle a WebSocket connection."""
        self.connections.append(websocket)
        try:
            async for message in websocket:
                await self.messages.put(message)
        finally:
            self.connections.remove(websocket)
    
    async def send_message(self, message):
        """Send a message to all connected clients."""
        if not isinstance(message, str):
            message = json.dumps(message)
        for conn in self.connections:
            await conn.send(message)

@pytest.fixture
async def mock_ws_server():
    """Create a mock WebSocket server."""
    import websockets
    
    server = MockWebSocketServer()
    async with websockets.serve(server.handler, 'localhost', 8765) as ws_server:
        yield server, ws_server

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
