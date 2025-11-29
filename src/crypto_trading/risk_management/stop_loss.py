""
Stop Loss Management Module

This module provides functionality for managing stop-loss orders,
including trailing stops and volatility-based stops.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Optional, Callable, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class StopType(Enum):
    """Types of stop loss orders"""
    FIXED = auto()
    TRAILING = auto()
    VOLATILITY = auto()
    TIME_BASED = auto()

@dataclass
class StopLossConfig:
    """Configuration for stop loss management"""
    initial_stop_pct: float = 0.02  # 2% initial stop loss
    trailing_stop_pct: float = 0.01  # 1% trailing stop
    volatility_multiplier: float = 2.0  # ATR multiplier for volatility stops
    max_loss_pct: float = 0.05  # Max 5% loss per trade
    time_based_stop_hours: int = 48  # Close position after 48 hours if not profitable
    use_trailing: bool = True
    use_volatility: bool = True

class TrailingStop:
    """Trailing stop implementation"""
    
    def __init__(self, config: Optional[StopLossConfig] = None):
        self.config = config or StopLossConfig()
        self.high_water_mark: Dict[str, float] = {}
        self.stop_prices: Dict[str, float] = {}
    
    def update(self, symbol: str, current_price: float) -> Optional[float]:
        """Update trailing stop and return stop price if triggered"""
        if symbol not in self.high_water_mark or current_price > self.high_water_mark[symbol]:
            self.high_water_mark[symbol] = current_price
            self.stop_prices[symbol] = current_price * (1 - self.config.trailing_stop_pct)
        
        if current_price <= self.stop_prices.get(symbol, 0):
            return self.stop_prices[symbol]
        return None

class StopLossManager:
    """Manages all stop loss functionality"""
    
    def __init__(self, config: Optional[StopLossConfig] = None):
        self.config = config or StopLossConfig()
        self.trailing_stop = TrailingStop(config)
        self.entry_prices: Dict[str, float] = {}
        self.entry_times: Dict[str, datetime] = {}
        self.volatility: Dict[str, float] = {}
    
    def set_entry(self, symbol: str, entry_price: float):
        """Set entry price and time for a position"""
        self.entry_prices[symbol] = entry_price
        self.entry_times[symbol] = datetime.utcnow()
        self.trailing_stop.high_water_mark[symbol] = entry_price
    
    def update_volatility(self, symbol: str, atr: float):
        """Update volatility measure (e.g., ATR) for a symbol"""
        self.volatility[symbol] = atr
    
    def check_stop_loss(
        self, 
        symbol: str, 
        current_price: float,
        position_size: float
    ) -> Optional[Dict[str, Any]]:
        """Check if any stop loss conditions are triggered"""
        if symbol not in self.entry_prices:
            return None
        
        entry_price = self.entry_prices[symbol]
        price_change_pct = (current_price - entry_price) / entry_price
        
        # Check fixed percentage stop loss
        if price_change_pct <= -self.config.initial_stop_pct:
            return {
                'type': 'fixed_percentage',
                'price': entry_price * (1 - self.config.initial_stop_pct),
                'reason': f'Price dropped below {self.config.initial_stop_pct*100}% stop loss'
            }
        
        # Check trailing stop
        if self.config.use_trailing:
            trailing_stop_price = self.trailing_stop.update(symbol, current_price)
            if trailing_stop_price and current_price <= trailing_stop_price:
                return {
                    'type': 'trailing',
                    'price': trailing_stop_price,
                    'reason': f'Trailing stop triggered at {trailing_stop_price}'
                }
        
        # Check volatility-based stop
        if self.config.use_volatility and symbol in self.volatility:
            atr = self.volatility[symbol]
            volatility_stop = entry_price - (atr * self.config.volatility_multiplier)
            if current_price <= volatility_stop:
                return {
                    'type': 'volatility',
                    'price': volatility_stop,
                    'reason': f'Volatility stop triggered (ATR: {atr:.2f})'
                }
        
        # Check time-based stop
        if symbol in self.entry_times:
            time_in_trade = datetime.utcnow() - self.entry_times[symbol]
            if time_in_trade >= timedelta(hours=self.config.time_based_stop_hours) and price_change_pct < 0:
                return {
                    'type': 'time_based',
                    'price': current_price,
                    'reason': f'Time-based stop after {self.config.time_based_stop_hours} hours with negative P&L'
                }
        
        return None

# Example usage
if __name__ == "__main__":
    # Initialize stop loss manager
    config = StopLossConfig(
        initial_stop_pct=0.02,    # 2% initial stop
        trailing_stop_pct=0.01,   # 1% trailing stop
        volatility_multiplier=2.0,
        max_loss_pct=0.05,        # 5% max loss per trade
        time_based_stop_hours=48  # Close after 48 hours if not profitable
    )
    
    stop_manager = StopLossManager(config)
    
    # Simulate a trade
    symbol = "BTC/USDT"
    entry_price = 50000.0
    stop_manager.set_entry(symbol, entry_price)
    stop_manager.update_volatility(symbol, atr=1000.0)  # Example ATR value
    
    # Simulate price movement
    prices = [51000, 52000, 51500, 50500, 49500, 49000, 50000, 51000, 50000, 49000]
    
    for price in prices:
        stop = stop_manager.check_stop_loss(symbol, price, 1.0)
        if stop:
            print(f"Stop loss triggered: {stop}")
            break
        print(f"Price: {price}, No stop triggered")
