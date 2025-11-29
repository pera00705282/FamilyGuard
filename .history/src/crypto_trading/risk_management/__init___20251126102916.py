"""
Risk Management Module

This package provides various risk management tools for crypto trading,
including position sizing, stop-loss management, correlation analysis, and hedging.
"""

from .position_sizing import PositionSizer, PositionSizingConfig, VolatilityPeriod
from .stop_loss import StopLossManager, StopLossConfig, StopType, TrailingStop
from .correlation import CorrelationMatrix, CorrelationConfig, PortfolioRiskAnalyzer
from .hedging import (
    HedgeManager, 
    HedgeConfig, 
    HedgeType, 
    HedgeStrategy, 
    DeltaNeutralStrategy
)

__all__ = [
    # Position Sizing
    'PositionSizer',
    'PositionSizingConfig',
    'VolatilityPeriod',
    
    # Stop Loss
    'StopLossManager',
    'StopLossConfig',
    'StopType',
    'TrailingStop',
    
    # Correlation Analysis
    'CorrelationMatrix',
    'CorrelationConfig',
    'PortfolioRiskAnalyzer',
    
    # Hedging
    'HedgeManager',
    'HedgeConfig',
    'HedgeType',
    'HedgeStrategy',
    'DeltaNeutralStrategy'
]
