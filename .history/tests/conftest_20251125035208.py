"""
Pytest configuration and fixtures for WebSocket testing.
"""
import asyncio
import json
import logging
import pytest
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, MagicMock, patch

# Configure test logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import WebSocket client with error handling
try:
    from crypto_trading.exchanges.websocket import (
        BaseWebSocketClient,
        BinanceWebSocketClient,
        TickerUpdate,
        OrderBookUpdate,
        Trade
    )
    WEBSOCKET_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import WebSocket modules: {e}")
    WEBSOCKET_AVAILABLE = False
    # Create dummy classes for testing
    class BaseWebSocketClient: pass
    class BinanceWebSocketClient: pass
    class TickerUpdate: pass
    class OrderBookUpdate: pass
    class Trade: pass

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

class MockWebSocketServer:
    """Mock WebSocket server for testing."""
    
    def __init__(self):
        self.messages = asyncio.Queue()
        self.connections: List[Any] = []
        self.connection_id = 0
    
    async def handler(self, websocket: Any, path: str) -> None:
        """Handle a WebSocket connection."""
        conn_id = self.connection_id
        self.connection_id += 1
        logger.info(f"New WebSocket connection: {conn_id}")
        
        self.connections.append(websocket)
        try:
            async for message in websocket:
                logger.debug(f"Received message from {conn_id}: {message}")
                await self.messages.put((conn_id, message))
        except Exception as e:
            logger.error(f"Error in WebSocket handler {conn_id}: {e}")
        finally:
            if websocket in self.connections:
                self.connections.remove(websocket)
            logger.info(f"WebSocket connection closed: {conn_id}")
    
    async def send_message(self, message: Union[str, Dict, bytes], conn_id: Optional[int] = None) -> None:
        """Send a message to connected clients.
        
        Args:
            message: Message to send (will be JSON-encoded if not a string)
            conn_id: If specified, only send to this connection ID
        """
        if not isinstance(message, (str, bytes)):
            message = json.dumps(message)
        
        targets = []
        if conn_id is not None:
            # Find connection by ID if specified
            for conn in self.connections:
                if id(conn) == conn_id:
                    targets.append(conn)
                    break
        else:
            # Send to all connections if no ID specified
            targets = self.connections.copy()
        
        for conn in targets:
            try:
                await conn.send(message)
                logger.debug(f"Sent message to connection {id(conn)}: {message}")
            except Exception as e:
                logger.error(f"Error sending message to {id(conn)}: {e}")
                if conn in self.connections:
                    self.connections.remove(conn)

# Fixtures
@pytest.fixture
def event_loop():
    """Create an instance of the default event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    
    # Cleanup
    if not loop.is_closed():
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

@pytest.fixture
def mock_websocket() -> MagicMock:
    """Create a mock WebSocket client with common methods."""
    ws = MagicMock()
    ws.recv = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.__aenter__.return_value = ws
    ws.__aexit__.return_value = None
    ws.closed = False
    return ws

@pytest.fixture
def binance_ws(mock_websocket: MagicMock) -> BinanceWebSocketClient:
    """Create a BinanceWebSocketClient with a mock WebSocket."""
    with patch('websockets.connect', return_value=mock_websocket):
        client = BinanceWebSocketClient()
        client._ws = mock_websocket
        return client

@pytest.fixture
async def mock_ws_server(event_loop) -> AsyncGenerator[Tuple[MockWebSocketServer, Any], None]:
    """Create a mock WebSocket server for testing."""
    try:
        import websockets
    except ImportError:
        pytest.skip("websockets package not available")
    
    server = MockWebSocketServer()
    port = 8765
    
    # Try to find an available port
    for _ in range(10):
        try:
            async with websockets.serve(server.handler, 'localhost', port) as ws_server:
                yield server, ws_server
                return
        except OSError as e:
            if "Address already in use" in str(e):
                port += 1
                continue
            raise
    
    raise RuntimeError("Could not find an available port for WebSocket server")

@pytest.fixture
def sample_ticker() -> Dict[str, Any]:
    """Return a sample ticker update."""
    return SAMPLE_TICKER.copy()

@pytest.fixture
def sample_combined_stream() -> Dict[str, Any]:
    """Return a sample combined stream message."""
    return SAMPLE_COMBINED_STREAM.copy()

@pytest.fixture
def sample_order_update() -> Dict[str, Any]:
    """Return a sample order update."""
    return SAMPLE_ORDER_UPDATE.copy()

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "websocket: mark test as requiring WebSocket support"
    )

# Add a skip decorator for when WebSocket tests can't run
if not WEBSOCKET_AVAILABLE:
    websocket_test = pytest.mark.skip(reason="WebSocket support not available")
else:
    websocket_test = lambda func: func  # noqa: E731
