"""
Custom metrics for tracking trading business logic.
"""
from prometheus_client import Counter, Gauge, Histogram, Summary
from typing import Optional, Dict, Any

class TradingMetrics:
    """Metrics collector for trading operations."""
    
    def __init__(self):
        # Trade execution metrics
        self.trades_executed = Counter(
            'trading_trades_executed_total',
            'Total number of trades executed',
            ['exchange', 'symbol', 'side']
        )
        
        self.trade_errors = Counter(
            'trading_trade_errors_total',
            'Total number of trade errors',
            ['exchange', 'symbol', 'error_type']
        )
        
        self.trade_amount = Gauge(
            'trading_trade_amount',
            'Amount of asset being traded',
            ['exchange', 'symbol', 'side']
        )
        
        self.trade_value = Gauge(
            'trading_trade_value',
            'Value of the trade in quote currency',
            ['exchange', 'symbol', 'side']
        )
        
        self.trade_latency = Histogram(
            'trading_trade_latency_seconds',
            'Latency of trade execution in seconds',
            ['exchange', 'symbol']
        )
        
        self.order_book_depth = Gauge(
            'trading_order_book_depth',
            'Current order book depth',
            ['exchange', 'symbol', 'side']
        )
        
        self.position_size = Gauge(
            'trading_position_size',
            'Current position size',
            ['exchange', 'symbol', 'side']
        )
        
        self.profit_loss = Gauge(
            'trading_profit_loss',
            'Current profit/loss',
            ['exchange', 'symbol']
        )
        
        self.slippage = Histogram(
            'trading_slippage_percent',
            'Slippage percentage per trade',
            ['exchange', 'symbol']
        )
        
        # Strategy metrics
        self.strategy_signals = Counter(
            'trading_strategy_signals_total',
            'Total number of trading signals generated',
            ['strategy', 'signal_type', 'symbol']
        )
        
        self.strategy_performance = Gauge(
            'trading_strategy_performance',
            'Performance metrics for strategies',
            ['strategy', 'metric', 'symbol']
        )
        
        # Risk metrics
        self.risk_exposure = Gauge(
            'trading_risk_exposure',
            'Current risk exposure',
            ['exchange', 'symbol', 'risk_type']
        )
        
        self.drawdown = Gauge(
            'trading_drawdown_percent',
            'Current drawdown percentage',
            ['exchange', 'symbol']
        )
    
    def record_trade(
        self,
        exchange: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        latency: Optional[float] = None
    ) -> None:
        """Record a trade execution."""
        labels = {'exchange': exchange, 'symbol': symbol, 'side': side}
        self.trades_executed.labels(**labels).inc()
        self.trade_amount.labels(**labels).set(amount)
        self.trade_value.labels(**labels).set(amount * price)
        
        if latency is not None:
            self.trade_latency.labels(exchange=exchange, symbol=symbol).observe(latency)
    
    def record_signal(self, strategy: str, signal_type: str, symbol: str) -> None:
        """Record a trading signal."""
        self.strategy_signals.labels(
            strategy=strategy,
            signal_type=signal_type,
            symbol=symbol
        ).inc()
    
    def update_position(
        self,
        exchange: str,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        current_price: float
    ) -> None:
        """Update position metrics."""
        self.position_size.labels(
            exchange=exchange,
            symbol=symbol,
            side=side
        ).set(size)
        
        # Calculate and update P&L
        if side == 'long':
            pnl = (current_price - entry_price) * size
        else:  # short
            pnl = (entry_price - current_price) * size
            
        self.profit_loss.labels(
            exchange=exchange,
            symbol=symbol
        ).set(pnl)

# Global instance
trading_metrics = TradingMetrics()
