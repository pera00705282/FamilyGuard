import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytest

from crypto_trading.strategies import (
    BaseStrategy,
    MarketData,
    MultiStrategyManager,
    Signal,
)


class DummyStrategy(BaseStrategy):
    """Lightweight strategy used for unit tests."""

    def __init__(self, name: str, action: Optional[str], base_strength: float = 0.5):
        super().__init__(name, params={"buffer_size": 10})
        self._action = action
        self._base_strength = base_strength

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        if not self._action:
            return None

        return Signal(
            symbol=symbol,
            action=self._action,
            strength=self._base_strength,
            price=data[-1].close,
            timestamp=data[-1].timestamp,
            strategy=self.name,
            metadata={"dummy": True},
        )


def sample_market_data(count: int = 5) -> List[MarketData]:
    base_time = datetime.now(timezone.utc)
    data = []
    price = 100.0
    for i in range(count):
        price += 1
        data.append(
            MarketData(
                symbol="BTC/USDT",
                timestamp=base_time + timedelta(minutes=i),
                open=price - 0.5,
                high=price + 0.5,
                low=price - 1.0,
                close=price,
                volume=100 + i,
            )
        )
    return data


@pytest.mark.asyncio
async def test_analyze_all_applies_weights():
    strategy = DummyStrategy("Dummy", "buy", base_strength=0.5)
    manager = MultiStrategyManager([strategy], weights={"Dummy": 2.0})

    signals = await manager.analyze_all("BTC/USDT", sample_market_data())

    assert len(signals) == 1
    assert signals[0].action == "buy"
    assert pytest.approx(signals[0].strength, rel=1e-5) == 1.0  # 0.5 * 2.0


def test_combine_signals_prefers_stronger_side():
    signals = [
        Signal(
            symbol="BTC/USDT",
            action="buy",
            strength=0.6,
            price=101,
            timestamp=datetime.now(timezone.utc),
            strategy="A",
        ),
        Signal(
            symbol="BTC/USDT",
            action="sell",
            strength=0.4,
            price=101,
            timestamp=datetime.now(timezone.utc),
            strategy="B",
        ),
    ]

    manager = MultiStrategyManager()
    final_signal = manager.combine_signals(signals)

    assert final_signal is not None
    assert final_signal.action == "buy"
    assert final_signal.strength == pytest.approx(0.6)
    assert final_signal.metadata["buy_signals"] == 1
    assert final_signal.metadata["sell_signals"] == 1


@pytest.mark.asyncio
async def test_get_combined_signals_uses_buffer_data():
    strategy_buy = DummyStrategy("BuyStrat", "buy", base_strength=0.6)
    strategy_sell = DummyStrategy("SellStrat", None)  # No signal
    manager = MultiStrategyManager(
        [strategy_buy, strategy_sell], weights={"BuyStrat": 1.0, "SellStrat": 1.0}
    )

    # Preload data into first strategy buffer so get_combined_signals can reuse it
    data = sample_market_data()
    for entry in data:
        strategy_buy.add_data("BTC/USDT", entry)

    combined = await manager.get_combined_signals("BTC/USDT")

    assert len(combined) == 1
    assert combined[0].action == "buy"


def test_get_strategy_performance_counts_data_and_signals():
    strategy = DummyStrategy("PerfStrat", "buy")
    strategy.signals.append(
        Signal(
            symbol="BTC/USDT",
            action="buy",
            strength=0.5,
            price=101,
            timestamp=datetime.now(timezone.utc),
            strategy="PerfStrat",
        )
    )
    for entry in sample_market_data(3):
        strategy.add_data("BTC/USDT", entry)

    manager = MultiStrategyManager([strategy])
    perf = manager.get_strategy_performance()

    assert perf["PerfStrat"]["total_signals"] == 1
    assert perf["PerfStrat"]["data_points"] == 3

