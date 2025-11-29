from collections import deque
from typing import Dict, Optional, Any
import numpy as np
import time

from .base_strategy import TradingStrategy, TradeSignal, SignalType

class MovingAverageCrossover(TradingStrategy):
    """
    Moving Average Crossover strategy that generates signals when a fast moving average
    crosses above or below a slow moving average.
    """
    
    def __init__(self, 
                 name: str, 
                 symbols: list[str], 
                 fast_window: int = 10, 
                 slow_window: int = 30,
                 min_confidence: float = 0.7):
        """
        Initialize the Moving Average Crossover strategy.
        
        Args:
            name: Strategy name
            symbols: List of trading symbols
            fast_window: Window size for fast moving average
            slow_window: Window size for slow moving average
            min_confidence: Minimum confidence threshold for signals (0-1)
        """
        super().__init__(name, symbols)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.min_confidence = min_confidence
        self.prices = {symbol: {
            'fast_ma': deque(maxlen=fast_window),
            'slow_ma': deque(maxlen=slow_window),
            'last_signal': None
        } for symbol in symbols}
        
    async def analyze(self, market_data: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trading signals based on MA crossover.
        
        Args:
            market_data: Dictionary containing market data with 'symbol' and 'close' price
            
        Returns:
            TradeSignal if a crossover is detected, None otherwise
        """
        symbol = market_data.get('symbol')
        price = market_data.get('close')
        
        if not symbol or price is None or symbol not in self.symbols:
            return None
            
        symbol_data = self.prices[symbol]
        symbol_data['fast_ma'].append(price)
        symbol_data['slow_ma'].append(price)
        
        # Need enough data points for both MAs
        if (len(symbol_data['fast_ma']) < self.fast_window or 
            len(symbol_data['slow_ma']) < self.slow_window):
            return None
            
        # Calculate moving averages
        fast_ma = sum(symbol_data['fast_ma']) / len(symbol_data['fast_ma'])
        slow_ma = sum(symbol_data['slow_ma']) / len(symbol_data['slow_ma'])
        
        # Calculate confidence based on the difference between MAs
        price_range = max(symbol_data['slow_ma']) - min(symbol_data['slow_ma'])
        ma_diff = abs(fast_ma - slow_ma)
        confidence = min(ma_diff / (price_range + 1e-10), 1.0)  # Avoid division by zero
        
        # Only proceed if confidence is above threshold
        if confidence < self.min_confidence:
            return None
            
        # Generate signals
        signal = None
        current_time = time.time()
        
        # Check for crossover
        if (fast_ma > slow_ma and 
            (not symbol_data['last_signal'] or 
             symbol_data['last_signal'].signal_type != SignalType.BUY)):
            signal = TradeSignal(
                signal_type=SignalType.BUY,
                symbol=symbol,
                price=price,
                timestamp=current_time,
                confidence=confidence,
                metadata={
                    'fast_ma': fast_ma,
                    'slow_ma': slow_ma,
                    'strategy': self.name
                }
            )
            symbol_data['last_signal'] = signal
            
        elif (fast_ma < slow_ma and 
              (not symbol_data['last_signal'] or 
               symbol_data['last_signal'].signal_type != SignalType.SELL)):
            signal = TradeSignal(
                signal_type=SignalType.SELL,
                symbol=symbol,
                price=price,
                timestamp=current_time,
                confidence=confidence,
                metadata={
                    'fast_ma': fast_ma,
                    'slow_ma': slow_ma,
                    'strategy': self.name
                }
            )
            symbol_data['last_signal'] = signal
            
        return signal
