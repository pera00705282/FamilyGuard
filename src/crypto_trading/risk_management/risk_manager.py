from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    entry_price: float
    size: float
    entry_time: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

class RiskManager:
    """
    Manages trading risk by enforcing position sizing, stop-loss, and daily loss limits.
    """
    
    def __init__(
        self,
        max_risk_per_trade: float = 0.02,  # 2% of account per trade
        max_daily_loss: float = 0.05,      # 5% max daily loss
        max_position_size: float = 0.1,    # 10% of account per position
        max_leverage: float = 10.0,        # 10x leverage max
        daily_reset_hour: int = 0          # UTC hour to reset daily metrics
    ):
        """
        Initialize the Risk Manager.
        
        Args:
            max_risk_per_trade: Maximum risk per trade as a fraction of account balance
            max_daily_loss: Maximum daily loss as a fraction of account balance
            max_position_size: Maximum position size as a fraction of account balance
            max_leverage: Maximum allowed leverage
            daily_reset_hour: UTC hour to reset daily metrics
        """
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_leverage = max_leverage
        self.daily_reset_hour = daily_reset_hour
        
        # State tracking
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_day = self._get_current_day()
        
    def _get_current_day(self) -> int:
        """Get the current day of the year (1-366)."""
        return datetime.utcnow().timetuple().tm_yday
    
    def _should_reset_daily_metrics(self) -> bool:
        """Check if daily metrics should be reset."""
        now = datetime.utcnow()
        current_day = self._get_current_day()
        
        if current_day != self.last_reset_day:
            if now.hour >= self.daily_reset_hour:
                self.last_reset_day = current_day
                return True
        return False
    
    def reset_daily_metrics(self) -> None:
        """Reset daily metrics."""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("Daily metrics reset")
    
    def update_daily_pnl(self, pnl: float) -> bool:
        """
        Update daily P&L and check if daily loss limit is exceeded.
        
        Args:
            pnl: Profit/loss amount to add to daily total
            
        Returns:
            bool: True if trading can continue, False if daily loss limit reached
        """
        if self._should_reset_daily_metrics():
            self.reset_daily_metrics()
            
        self.daily_pnl += pnl
        self.daily_trades += 1
        
        if self.daily_pnl < -self.max_daily_loss:
            logger.warning(
                f"Daily loss limit reached: {self.daily_pnl:.2%} "
                f"(limit: {-self.max_daily_loss:.2%})"
            )
            return False
            
        return True
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_balance: float,
        current_positions: Optional[Dict[str, float]] = None
    ) -> Tuple[float, Dict]:
        """
        Calculate the optimal position size based on risk parameters.
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price for the position
            stop_loss: Stop loss price
            account_balance: Current account balance
            current_positions: Dictionary of current positions with their values
            
        Returns:
            Tuple of (position_size, metadata) where metadata contains calculation details
        """
        if account_balance <= 0:
            return 0.0, {"error": "Invalid account balance"}
            
        if entry_price <= 0 or stop_loss <= 0:
            return 0.0, {"error": "Invalid price or stop loss"}
            
        # Calculate risk per unit
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 0.0, {"error": "Stop loss too close to entry price"}
            
        # Calculate position size based on risk per trade
        risk_amount = account_balance * self.max_risk_per_trade
        position_size = risk_amount / risk_per_share
        
        # Calculate position value
        position_value = position_size * entry_price
        max_position_value = account_balance * self.max_position_size
        
        # Apply position size limit
        if position_value > max_position_value:
            position_size = max_position_value / entry_price
            position_value = max_position_value
            logger.info(f"Position size capped at {self.max_position_size:.1%} of account")
        
        # Check total exposure if current positions are provided
        if current_positions:
            total_exposure = sum(current_positions.values()) + position_value
            if total_exposure > account_balance * self.max_leverage:
                available = (account_balance * self.max_leverage) - \
                           (sum(current_positions.values()))
                if available <= 0:
                    return 0.0, {"error": "Max leverage reached"}
                position_size = available / entry_price
                position_value = available
                logger.info(f"Position size reduced to stay within leverage limits")
        
        # Calculate risk/reward ratio (assuming take profit at 2x risk)
        take_profit = entry_price + 2 * (entry_price - stop_loss)
        risk_reward = (take_profit - entry_price) / (entry_price - stop_loss)
        
        metadata = {
            "risk_per_share": risk_per_share,
            "risk_amount": risk_amount,
            "position_value": position_value,
            "risk_percent": self.max_risk_per_trade,
            "leverage": position_value / account_balance,
            "risk_reward_ratio": risk_reward,
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
        
        return position_size, metadata
    
    def validate_order(
        self,
        symbol: str,
        order_type: str,
        price: float,
        size: float,
        account_balance: float,
        current_positions: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, str]:
        """
        Validate an order against risk parameters.
        
        Args:
            symbol: Trading pair symbol
            order_type: Type of order (e.g., 'buy', 'sell')
            price: Order price
            size: Order size in base currency
            account_balance: Current account balance
            current_positions: Dictionary of current positions with their values
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if account_balance <= 0:
            return False, "Invalid account balance"
            
        if price <= 0 or size <= 0:
            return False, "Invalid price or size"
            
        position_value = price * size
        
        # Check position size limit
        if position_value > account_balance * self.max_position_size:
            return False, f"Position size {position_value:.2f} exceeds {self.max_position_size:.1%} limit"
            
        # Check leverage limit if current_positions is provided
        if current_positions is not None:
            total_exposure = sum(current_positions.values())
            if order_type.lower() == 'buy':
                total_exposure += position_value
                
            leverage = total_exposure / account_balance
            if leverage > self.max_leverage:
                return False, f"Leverage {leverage:.1f}x exceeds maximum {self.max_leverage}x"
                
        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss * account_balance:
            return False, "Daily loss limit reached"
            
        return True, ""
    
    def update_position(
        self,
        symbol: str,
        entry_price: float,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Update or create a position.
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            size: Position size (positive for long, negative for short)
            stop_loss: Stop loss price
            take_profit: Take profit price
            metadata: Additional position metadata
        """
        if size == 0:
            if symbol in self.positions:
                del self.positions[symbol]
            return
            
        if symbol in self.positions:
            # Update existing position
            position = self.positions[symbol]
            total_size = position.size + size
            
            if total_size == 0:
                # Position closed
                del self.positions[symbol]
                return
                
            # Calculate volume-weighted average price
            position.entry_price = (
                (position.entry_price * position.size + entry_price * size) / 
                (position.size + size)
            )
            position.size = total_size
            
            # Update stop loss and take profit if provided
            if stop_loss is not None:
                position.stop_loss = stop_loss
            if take_profit is not None:
                position.take_profit = take_profit
                
            if metadata:
                position.metadata.update(metadata)
        else:
            # Create new position
            self.positions[symbol] = Position(
                symbol=symbol,
                entry_price=entry_price,
                size=size,
                entry_time=time.time(),
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata=metadata or {}
            )
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get the current position for a symbol."""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, Position]:
        """Get all current positions."""
        return self.positions.copy()
    
    def get_position_value(self, symbol: str, current_price: float) -> float:
        """Calculate the current value of a position."""
        position = self.positions.get(symbol)
        if not position:
            return 0.0
        return position.size * current_price
    
    def get_total_exposure(self, current_prices: Dict[str, float]) -> float:
        """Calculate the total exposure across all positions."""
        return sum(
            pos.size * current_prices.get(pos.symbol, 0)
            for pos in self.positions.values()
        )
    
    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate unrealized P&L for all positions."""
        pnl = {}
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                pnl[symbol] = (current_prices[symbol] - position.entry_price) * position.size
        return pnl
