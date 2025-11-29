"""
Metrics for tracking trading strategy performance.
"""
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from prometheus_client import Gauge, Counter, Histogram, Summary

@dataclass
class TradeMetrics:
    """Track metrics for individual trades."""
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    
    def close_trade(self, exit_price: float) -> None:
        """Record trade exit and calculate P&L."""
        self.exit_price = exit_price
        self.exit_time = datetime.utcnow()
        self.pnl = exit_price - self.entry_price
        self.pnl_pct = (self.pnl / self.entry_price) * 100

class StrategyMetrics:
    """Track metrics for trading strategies."""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        
        # Trade execution metrics
        self.trades_total = Counter(
            f'trading_strategy_{strategy_name}_trades_total',
            f'Total number of trades for {strategy_name}',
            ['symbol', 'side']
        )
        
        self.trade_pnl = Gauge(
            f'trading_strategy_{strategy_name}_pnl',
            f'Profit and loss for {strategy_name}',
            ['symbol', 'trade_id']
        )
        
        # Performance metrics
        self.win_rate = Gauge(
            f'trading_strategy_{strategy_name}_win_rate',
            f'Win rate for {strategy_name}',
            ['symbol']
        )
        
        self.profit_factor = Gauge(
            f'trading_strategy_{strategy_name}_profit_factor',
            f'Profit factor for {strategy_name}',
            ['symbol']
        )
        
        self.max_drawdown = Gauge(
            f'trading_strategy_{strategy_name}_max_drawdown',
            f'Maximum drawdown for {strategy_name}',
            ['symbol']
        )
        
        self.sharpe_ratio = Gauge(
            f'trading_strategy_{strategy_name}_sharpe_ratio',
            f'Sharpe ratio for {strategy_name}',
            ['symbol']
        )
        
        # Trade analysis
        self.avg_trade_duration = Gauge(
            f'trading_strategy_{strategy_name}_avg_trade_duration_seconds',
            f'Average trade duration in seconds for {strategy_name}',
            ['symbol']
        )
        
        self.avg_win_loss_ratio = Gauge(
            f'trading_strategy_{strategy_name}_avg_win_loss_ratio',
            f'Average win/loss ratio for {strategy_name}',
            ['symbol']
        )
        
        # Risk metrics
        self.risk_reward_ratio = Gauge(
            f'trading_strategy_{strategy_name}_risk_reward_ratio',
            f'Average risk/reward ratio for {strategy_name}',
            ['symbol']
        )
        
        self.volatility = Gauge(
            f'trading_strategy_{strategy_name}_volatility',
            f'Volatility of returns for {strategy_name}',
            ['symbol']
        )
        
        # Track active trades
        self._active_trades: Dict[str, Dict[str, TradeMetrics]] = {}
        self._trade_history: Dict[str, List[TradeMetrics]] = {}
    
    def record_trade_entry(self, trade_id: str, symbol: str, side: str, price: float) -> None:
        """Record a new trade entry."""
        self.trades_total.labels(symbol=symbol, side=side).inc()
        
        if symbol not in self._active_trades:
            self._active_trades[symbol] = {}
            self._trade_history[symbol] = []
            
        self._active_trades[symbol][trade_id] = TradeMetrics(entry_price=price)
    
    def record_trade_exit(self, trade_id: str, symbol: str, exit_price: float) -> None:
        """Record trade exit and update metrics."""
        if symbol not in self._active_trades or trade_id not in self._active_trades[symbol]:
            return
            
        trade = self._active_trades[symbol].pop(trade_id)
        trade.close_trade(exit_price)
        self._trade_history[symbol].append(trade)
        
        # Update P&L gauge
        self.trade_pnl.labels(symbol=symbol, trade_id=trade_id).set(trade.pnl_pct or 0)
        
        # Update performance metrics
        self._update_performance_metrics(symbol)
    
    def _update_performance_metrics(self, symbol: str) -> None:
        """Update performance metrics based on trade history."""
        trades = self._trade_history.get(symbol, [])
        if not trades:
            return
        
        # Calculate win rate
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        self.win_rate.labels(symbol=symbol).set(
            (len(winning_trades) / len(trades)) * 100 if trades else 0
        )
        
        # Calculate profit factor
        gross_profit = sum(t.pnl for t in trades if t.pnl and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl and t.pnl < 0))
        self.profit_factor.labels(symbol=symbol).set(
            gross_profit / gross_loss if gross_loss != 0 else float('inf')
        )
        
        # Calculate max drawdown
        equity_curve = np.cumsum([t.pnl or 0 for t in trades])
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - running_max) / running_max * 100
        self.max_drawdown.labels(symbol=symbol).set(
            np.min(drawdowns) if len(drawdowns) > 0 else 0
        )
        
        # Calculate Sharpe ratio (assuming 0% risk-free rate for simplicity)
        returns = [t.pnl_pct or 0 for t in trades if t.pnl_pct is not None]
        if len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
            self.sharpe_ratio.labels(symbol=symbol).set(sharpe)
        
        # Calculate average trade duration
        durations = [
            (t.exit_time - t.entry_time).total_seconds()
            for t in trades if t.exit_time and t.entry_time
        ]
        if durations:
            self.avg_trade_duration.labels(symbol=symbol).set(np.mean(durations))
        
        # Calculate average win/loss ratio
        wins = [t.pnl_pct for t in trades if t.pnl_pct and t.pnl_pct > 0]
        losses = [abs(t.pnl_pct) for t in trades if t.pnl_pct and t.pnl_pct < 0]
        
        if wins and losses:
            self.avg_win_loss_ratio.labels(symbol=symbol).set(
                np.mean(wins) / np.mean(losses)
            )
        
        # Update risk metrics
        if len(returns) > 1:
            self.volatility.labels(symbol=symbol).set(np.std(returns) * np.sqrt(252))  # Annualized
            
            # Calculate average risk/reward ratio
            avg_win = np.mean([t.pnl_pct for t in trades if t.pnl_pct and t.pnl_pct > 0] or [0])
            avg_loss = abs(np.mean([t.pnl_pct for t in trades if t.pnl_pct and t.pnl_pct < 0] or [0]))
            if avg_loss > 0:
                self.risk_reward_ratio.labels(symbol=symbol).set(avg_win / avg_loss)

# Global instance for quick access
strategy_metrics = StrategyMetrics("default")
