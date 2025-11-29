""
Risk Management Module

This package contains components for managing risk in algorithmic trading,
including position sizing, stop-loss management, and portfolio risk analysis.
"""

from .position_sizing import PositionSizer, PositionSizingConfig
from .stop_loss import TrailingStop, StopLossManager
from .correlation import CorrelationMatrix, PortfolioRiskAnalyzer
from .hedging import HedgeManager, HedgeStrategy

__all__ = [
    'PositionSizer',
    'PositionSizingConfig',
    'TrailingStop',
    'StopLossManager',
    'CorrelationMatrix',
    'PortfolioRiskAnalyzer',
    'HedgeManager',
    'HedgeStrategy'
]
