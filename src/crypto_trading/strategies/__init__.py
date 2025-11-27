"""Trading strategies module"""

from .manager import (
    BaseStrategy,
    MovingAverageCrossStrategy,
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    VolumeWeightedStrategy,
    MultiStrategyManager,
    MarketData,
    Signal,
    create_conservative_strategy,
    create_aggressive_strategy,
)

__all__ = [
    "BaseStrategy",
    "MovingAverageCrossStrategy",
    "RSIStrategy",
    "MACDStrategy",
    "BollingerBandsStrategy",
    "VolumeWeightedStrategy",
    "MultiStrategyManager",
    "MarketData",
    "Signal",
    "create_conservative_strategy",
    "create_aggressive_strategy",
]
