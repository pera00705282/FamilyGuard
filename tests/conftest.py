"""Pytest configuration and fixtures."""
import asyncio
import os
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock

# Set test environment
os.environ['ENVIRONMENT'] = 'test'

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_websocket() -> MagicMock:
    """Create a mock WebSocket connection."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    return ws

@pytest.fixture
def sample_ticker_message() -> dict:
    """Return a sample ticker message."""
    return {
        "e": "24hrTicker",
        "E": 123456789,
        "s": "BTCUSDT",
        "p": "100.0",
        "P": "1.0",
        "w": "10000.0",
        "c": "10100.0",
        "Q": "1.0",
        "o": "10000.0",
        "h": "10200.0",
        "l": "9900.0",
        "v": "1000.0",
        "q": "10000000.0",
        "O": 0,
        "C": 0,
        "F": 0,
        "L": 0,
        "n": 0
    }
