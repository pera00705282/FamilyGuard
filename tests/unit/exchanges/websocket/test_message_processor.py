import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from datetime import datetime

from src.crypto_trading.exchanges.websocket.message_processor import (
    MessageProcessor,
    WebSocketMessage
)

@pytest.mark.asyncio
class TestMessageProcessor:
    """Test the MessageProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a MessageProcessor instance for testing."""
        return MessageProcessor(
            max_batch_size=5,
            max_batch_time=0.1,
            max_workers=2
        )
        
    async def test_process_single_message(self, processor):
        """Test processing a single message."""
        callback = AsyncMock()
        processor.register_callback('message', callback)
        
        msg = WebSocketMessage(
            data={'test': 'data'},
            received_at=time.time(),
            exchange='test',
            channel='test',
            symbol='BTC/USDT'
        )
        
        await processor.process_message(msg)
        await asyncio.sleep(0.1)  # Allow time for processing
        
        callback.assert_awaited()
        args = callback.await_args[0][0]
        assert args['event'] in ['start', 'complete']
        assert args['message'] == msg
