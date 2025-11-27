"""
Tests for trading strategies
"""

import pytest  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
import numpy as np  # pyright: ignore[reportMissingImports]

from crypto_trading.strategies import (
    MovingAverageCrossStrategy,
    MarketData
)


@pytest.fixture
def sample_market_data():
    """Generate sample market data for testing"""
    data = []
    base_price = 50000.0
    for i in range(100):
        # Generate realistic price movement
        price_change = np.random.normal(0, 0.02)  # 2% volatility
        base_price *= 1 + price_change
        # Generate volume
        volume = np.random.uniform(100, 1000)
        market_data = MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.now() - timedelta(hours=100 - i),
            open=base_price * 0.999,
            high=base_price * 1.001,
            low=base_price * 0.998,
            close=base_price,
            volume=volume,
        )
        data.append(market_data)
    return data


class TestMovingAverageCrossStrategy:
    """Test Moving Average Cross Strategy"""

    def test_initialization(self):
        strategy = MovingAverageCrossStrategy(fast_period=10, slow_period=30)
        assert strategy.name == "MA_Cross"
        assert strategy.params["fast_period"] == 10
        assert strategy.params["slow_period"] == 30


@pytest.mark.asyncio
async def test_analyze_insufficient_data():
    strategy = MovingAverageCrossStrategy(fast_period=10, slow_period=30)
    # Test with insufficient data
    data = [
        MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            open=50000,
            high=50100,
            low=49900,
            close=50000,
            volume=100,
        )
    ]
    signal = await strategy.analyze("BTC/USDT", data)
    assert signal is None


if __name__ == "__main__":
    pytest.main([__file__])
