""
Dynamic Position Sizing Module

This module implements position sizing strategies based on market volatility,
account size, and risk tolerance.
"""
from typing import Dict, Optional, Union
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum, auto
import logging

logger = logging.getLogger(__name__)

class VolatilityPeriod(Enum):
    """Time periods for volatility calculation"""
    SHORT_TERM = auto()  # Last 7 days
    MEDIUM_TERM = auto()  # Last 30 days
    LONG_TERM = auto()   # Last 90 days

@dataclass
class PositionSizingConfig:
    """Configuration for position sizing"""
    account_size: float = 10000.0
    max_risk_per_trade: float = 0.01  # 1% of account per trade
    max_portfolio_risk: float = 0.10  # 10% of account at risk
    volatility_lookback: int = 20     # Number of periods for volatility calculation
    atr_period: int = 14             # ATR period for volatility measurement
    min_position_size: float = 0.01   # Minimum position size in base currency
    max_position_size: float = 0.1    # Maximum position size as % of account
    volatility_adjustment: bool = True
    correlation_adjustment: bool = True

class PositionSizer:
    """
    Calculates optimal position size based on volatility and risk parameters.
    """
    
    def __init__(self, config: Optional[PositionSizingConfig] = None):
        self.config = config or PositionSizingConfig()
        self.positions = {}
        
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        current_volatility: Optional[float] = None,
        correlation_matrix: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Calculate position size based on risk parameters and market conditions.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            entry_price: Entry price for the position
            stop_loss: Stop loss price
            current_volatility: Current volatility (ATR or standard deviation)
            correlation_matrix: Correlation matrix for correlation adjustment
            
        Returns:
            Dictionary containing position sizing details
        """
        # Calculate basic risk per share
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            raise ValueError("Stop loss cannot be equal to entry price")
        
        # Calculate base position size
        max_risk_amount = self.config.account_size * self.config.max_risk_per_trade
        base_position_size = max_risk_amount / risk_per_share
        
        # Apply volatility adjustment if enabled
        if self.config.volatility_adjustment and current_volatility is not None:
            position_size = self._adjust_for_volatility(base_position_size, current_volatility)
        else:
            position_size = base_position_size
        
        # Apply correlation adjustment if enabled
        if self.config.correlation_adjustment and correlation_matrix is not None:
            position_size = self._adjust_for_correlation(
                symbol, position_size, correlation_matrix
            )
        
        # Apply position size limits
        position_value = position_size * entry_price
        max_position_value = self.config.account_size * self.config.max_position_size
        position_size = min(position_size, max_position_value / entry_price)
        position_size = max(position_size, self.config.min_position_size)
        
        # Calculate position metrics
        position_risk = position_size * risk_per_share
        risk_percentage = (position_risk / self.config.account_size) * 100
        
        return {
            'position_size': position_size,
            'position_value': position_size * entry_price,
            'risk_amount': position_risk,
            'risk_percentage': risk_percentage,
            'leverage': (position_size * entry_price) / max_risk_amount
        }
    
    def _adjust_for_volatility(self, position_size: float, volatility: float) -> float:
        """Adjust position size based on current market volatility."""
        # Normalize volatility (e.g., using ATR/price ratio)
        volatility_ratio = volatility / position_size if position_size > 0 else 1.0
        
        # Reduce position size as volatility increases
        # Using inverse square root for smoother scaling
        adjustment = 1.0 / np.sqrt(1.0 + volatility_ratio)
        
        return position_size * adjustment
    
    def _adjust_for_correlation(
        self,
        symbol: str,
        position_size: float,
        correlation_matrix: pd.DataFrame
    ) -> float:
        """Adjust position size based on correlation with existing positions."""
        if symbol not in correlation_matrix.columns:
            logger.warning(f"Symbol {symbol} not found in correlation matrix")
            return position_size
        
        # Calculate weighted average correlation with existing positions
        total_correlation = 0.0
        total_weight = 0.0
        
        for pos_symbol, pos_data in self.positions.items():
            if pos_symbol in correlation_matrix.columns:
                weight = pos_data['position_value'] / self.config.account_size
                corr = correlation_matrix.loc[symbol, pos_symbol]
                total_correlation += corr * weight
                total_weight += weight
        
        if total_weight > 0:
            avg_correlation = total_correlation / total_weight
            # Reduce position size for highly correlated positions
            correlation_factor = 1.0 - (0.5 * abs(avg_correlation))
            return position_size * correlation_factor
        
        return position_size
    
    def update_position(self, symbol: str, position_data: Dict[str, float]) -> None:
        """Update internal tracking of open positions."""
        self.positions[symbol] = position_data
    
    def remove_position(self, symbol: str) -> None:
        """Remove a closed position from tracking."""
        self.positions.pop(symbol, None)

# Example usage
if __name__ == "__main__":
    # Initialize position sizer
    config = PositionSizingConfig(
        account_size=50000.0,
        max_risk_per_trade=0.02,  # 2% risk per trade
        max_position_size=0.2,    # Max 20% of account in one position
    )
    sizer = PositionSizer(config)
    
    # Example trade
    entry_price = 50000.0  # BTC/USDT price
    stop_loss = 48000.0    # 4% stop loss
    
    # Calculate position size
    position = sizer.calculate_position_size(
        symbol="BTC/USDT",
        entry_price=entry_price,
        stop_loss=stop_loss,
        current_volatility=2000.0  # Example ATR value
    )
    
    print(f"Position size: {position['position_size']:.4f} BTC")
    print(f"Position value: ${position['position_value']:.2f}")
    print(f"Risk amount: ${position['risk_amount']:.2f} ({position['risk_percentage']:.2f}% of account)")
