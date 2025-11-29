from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TradeSignal:
    signal_type: SignalType
    symbol: str
    price: float
    timestamp: float
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None

class TradingStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    def __init__(self, name: str, symbols: list[str]):
        self.name = name
        self.symbols = symbols
        self.is_active = False
        
    async def initialize(self) -> None:
        """Initialize the strategy and any required resources."""
        self.is_active = True
        logger.info(f"Initialized strategy: {self.name}")
    
    async def shutdown(self) -> None:
        """Clean up resources used by the strategy."""
        self.is_active = False
        logger.info(f"Shut down strategy: {self.name}")
    
    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trading signals.
        
        Args:
            market_data: Dictionary containing market data (OHLCV, order book, etc.)
            
        Returns:
            TradeSignal if a trading opportunity is found, None otherwise
        """
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', symbols={self.symbols})"
