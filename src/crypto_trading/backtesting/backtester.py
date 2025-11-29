from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from ..strategies.base_strategy import TradingStrategy, TradeSignal, SignalType
from ..risk_management.risk_manager import RiskManager, Position

logger = logging.getLogger(__name__)

class BacktestResult:
    """Container for backtesting results and metrics."""
    
    def __init__(self):
        self.trades = []
        self.equity_curve = []
        self.metrics = {}
        self.signals = []
        self.timestamps = []
        
    def add_trade(self, trade: Dict[str, Any]) -> None:
        """Add a trade to the results."""
        self.trades.append(trade)
        
    def add_equity_point(self, timestamp: datetime, equity: float) -> None:
        """Add an equity point to the equity curve."""
        self.equity_curve.append({"timestamp": timestamp, "equity": equity})
        self.timestamps.append(timestamp)
        
    def add_signal(self, signal: TradeSignal) -> None:
        """Add a trading signal."""
        self.signals.append({
            "timestamp": datetime.fromtimestamp(signal.timestamp),
            "symbol": signal.symbol,
            "signal": signal.signal_type.value,
            "price": signal.price,
            "confidence": signal.confidence,
            **signal.metadata
        })
        
    def calculate_metrics(self, initial_balance: float) -> Dict[str, Any]:
        """Calculate performance metrics from the backtest results."""
        if not self.trades:
            return {}
            
        df_trades = pd.DataFrame(self.trades)
        df_equity = pd.DataFrame(self.equity_curve)
        
        # Basic metrics
        total_return = (df_equity["equity"].iloc[-1] / initial_balance - 1) * 100
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades["pnl"] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = df_trades["pnl"].sum()
        avg_win = df_trades[df_trades["pnl"] > 0]["pnl"].mean() if winning_trades > 0 else 0
        avg_loss = abs(df_trades[df_trades["pnl"] <= 0]["pnl"].mean()) if losing_trades > 0 else 0
        profit_factor = -avg_win * winning_trades / (avg_loss * losing_trades) if losing_trades > 0 else float('inf')
        
        # Risk metrics
        max_drawdown = self._calculate_max_drawdown(df_equity["equity"])
        sharpe_ratio = self._calculate_sharpe_ratio(df_equity["equity"])
        sortino_ratio = self._calculate_sortino_ratio(df_equity["equity"])
        
        # Trade metrics
        avg_trade_duration = (df_trades["exit_time"] - df_trades["entry_time"]).mean().total_seconds() / 3600
        
        self.metrics = {
            "initial_balance": initial_balance,
            "final_balance": df_equity["equity"].iloc[-1],
            "total_return_pct": total_return,
            "total_return": df_equity["equity"].iloc[-1] - initial_balance,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_win_loss_ratio": avg_win / avg_loss if avg_loss != 0 else float('inf'),
            "avg_trade_duration_hours": avg_trade_duration,
            "trades_per_day": total_trades / ((df_equity["timestamp"].max() - df_equity["timestamp"].min()).days or 1),
        }
        
        return self.metrics
    
    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculate maximum drawdown."""
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        return drawdown.min()
    
    def _calculate_sharpe_ratio(self, equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio."""
        returns = equity_curve.pct_change().dropna()
        if len(returns) < 2:
            return 0.0
            
        excess_returns = returns - risk_free_rate / 252  # Assuming daily data
        return np.sqrt(252) * excess_returns.mean() / (returns.std() + 1e-10)
    
    def _calculate_sortino_ratio(self, equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Calculate annualized Sortino ratio."""
        returns = equity_curve.pct_change().dropna()
        if len(returns) < 2:
            return 0.0
            
        excess_returns = returns - risk_free_rate / 252  # Assuming daily data
        downside_returns = returns[returns < 0]
        downside_std = np.sqrt((downside_returns ** 2).mean()) if len(downside_returns) > 0 else 0
        
        return np.sqrt(252) * excess_returns.mean() / (downside_std + 1e-10)
    
    def get_trade_history(self) -> pd.DataFrame:
        """Get trade history as a pandas DataFrame."""
        return pd.DataFrame(self.trades)
    
    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as a pandas DataFrame."""
        return pd.DataFrame(self.equity_curve)
    
    def get_signals(self) -> pd.DataFrame:
        """Get trading signals as a pandas DataFrame."""
        return pd.DataFrame(self.signals)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get calculated performance metrics."""
        return self.metrics


class Backtester:
    """
    Backtesting engine for evaluating trading strategies on historical data.
    """
    
    def __init__(
        self,
        strategy: TradingStrategy,
        initial_balance: float = 10000.0,
        commission: float = 0.001,  # 0.1% commission per trade
        slippage: float = 0.0005,   # 0.05% slippage per trade
        risk_free_rate: float = 0.0,
    ):
        """
        Initialize the backtester.
        
        Args:
            strategy: Trading strategy to backtest
            initial_balance: Initial account balance in quote currency
            commission: Commission rate per trade (e.g., 0.001 for 0.1%)
            slippage: Slippage rate per trade (e.g., 0.0005 for 0.05%)
            risk_free_rate: Annual risk-free rate for performance metrics
        """
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.commission = commission
        self.slippage = slippage
        self.risk_free_rate = risk_free_rate
        
        # Initialize risk manager
        self.risk_manager = RiskManager()
        
        # State tracking
        self.balance = initial_balance
        self.equity = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trade_history = []
        self.equity_curve = []
        self.current_prices: Dict[str, float] = {}
        
        # Results
        self.results = BacktestResult()
        
    async def run(self, data: Dict[str, pd.DataFrame]) -> BacktestResult:
        """
        Run the backtest on the provided historical data.
        
        Args:
            data: Dictionary of DataFrames with historical data for each symbol
            
        Returns:
            BacktestResult containing the backtest results and metrics
        """
        logger.info(f"Starting backtest with initial balance: {self.initial_balance:.2f}")
        
        # Initialize strategy
        await self.strategy.initialize()
        
        try:
            # Convert data to a list of (timestamp, symbol, row) tuples
            data_points = self._prepare_data(data)
            
            # Process each data point in chronological order
            for timestamp, symbol, row in data_points:
                # Update current price
                self.current_prices[symbol] = row["close"]
                
                # Update positions and calculate equity
                self._update_positions(timestamp)
                
                # Record equity curve
                self._record_equity(timestamp)
                
                # Get market data for strategy
                market_data = self._prepare_market_data(symbol, row, timestamp)
                
                # Get trading signal from strategy
                signal = await self.strategy.analyze(market_data)
                
                if signal:
                    # Record the signal
                    self.results.add_signal(signal)
                    
                    # Execute the signal
                    await self._execute_signal(signal, timestamp)
            
            # Close all positions at the end of the backtest
            self._close_all_positions(timestamp)
            
            # Calculate final metrics
            self.results.calculate_metrics(self.initial_balance)
            
            logger.info("Backtest completed successfully")
            logger.info(f"Final balance: {self.balance + self._get_positions_value():.2f}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"Error during backtest: {e}", exc_info=True)
            raise
            
        finally:
            # Clean up
            await self.strategy.shutdown()
    
    def _prepare_data(self, data: Dict[str, pd.DataFrame]) -> List[Tuple[datetime, str, pd.Series]]:
        """Prepare and sort the data for processing."""
        data_points = []
        
        for symbol, df in data.items():
            # Ensure the index is a datetime
            df = df.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
                
            # Add each row to the data points
            for ts, row in df.iterrows():
                data_points.append((ts, symbol, row))
        
        # Sort by timestamp
        data_points.sort(key=lambda x: x[0])
        
        return data_points
    
    def _prepare_market_data(self, symbol: str, row: pd.Series, timestamp: datetime) -> Dict[str, Any]:
        """Prepare market data for the strategy."""
        return {
            "symbol": symbol,
            "timestamp": timestamp.timestamp(),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row.get("volume", 0),
            "current_price": row["close"],
            "positions": self.positions.copy(),
            "balance": self.balance,
            "equity": self.equity,
        }
    
    def _update_positions(self, timestamp: datetime) -> None:
        """Update open positions and calculate unrealized P&L."""
        positions_value = 0.0
        
        for symbol, position in list(self.positions.items()):
            if symbol in self.current_prices:
                current_price = self.current_prices[symbol]
                position.unrealized_pnl = (current_price - position.entry_price) * position.size
                positions_value += position.size * current_price
                
                # Check for stop loss/take profit
                if position.stop_loss is not None and position.size > 0 and current_price <= position.stop_loss:
                    self._close_position(position, timestamp, "stop_loss")
                elif position.take_profit is not None and position.size > 0 and current_price >= position.take_profit:
                    self._close_position(position, timestamp, "take_profit")
                
        self.equity = self.balance + positions_value
    
    def _record_equity(self, timestamp: datetime) -> None:
        """Record the current equity value."""
        self.equity_curve.append({"timestamp": timestamp, "equity": self.equity})
        self.results.add_equity_point(timestamp, self.equity)
    
    async def _execute_signal(self, signal: TradeSignal, timestamp: datetime) -> None:
        """Execute a trading signal."""
        symbol = signal.signal.symbol
        price = signal.price
        
        # Apply slippage
        if signal.signal_type == SignalType.BUY:
            price *= (1 + self.slippage)
        else:  # SELL
            price *= (1 - self.slippage)
        
        # Calculate position size based on risk management
        position_size, metadata = self._calculate_position_size(signal, price)
        
        if position_size == 0:
            return
        
        # Execute the trade
        if signal.signal_type == SignalType.BUY:
            await self._enter_position(symbol, price, position_size, timestamp, metadata)
        else:  # SELL
            await self._exit_position(symbol, price, position_size, timestamp, metadata)
    
    def _calculate_position_size(
        self, signal: TradeSignal, price: float
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate position size based on risk management rules."""
        # Get current positions value
        current_positions = {
            sym: pos.size * self.current_prices.get(sym, 0)
            for sym, pos in self.positions.items()
        }
        
        # Calculate position size using risk manager
        stop_loss = signal.metadata.get("stop_loss")
        if stop_loss is None:
            # Default stop loss if not provided
            stop_loss = price * (0.95 if signal.signal_type == SignalType.BUY else 1.05)
        
        position_size, metadata = self.risk_manager.calculate_position_size(
            symbol=signal.signal.symbol,
            entry_price=price,
            stop_loss=stop_loss,
            account_balance=self.equity,
            current_positions=current_positions
        )
        
        return position_size, metadata
    
    async def _enter_position(
        self, symbol: str, price: float, size: float, timestamp: datetime, metadata: Dict[str, Any]
    ) -> None:
        """Enter a new position."""
        # Calculate position value and commission
        position_value = price * size
        commission = position_value * self.commission
        
        # Check if we have enough balance
        if position_value + commission > self.balance:
            logger.warning(f"Insufficient balance to enter position: {position_value:.2f} > {self.balance:.2f}")
            return
        
        # Update balance
        self.balance -= (position_value + commission)
        
        # Create or update position
        if symbol in self.positions:
            position = self.positions[symbol]
            # Average the entry price
            total_size = position.size + size
            position.entry_price = (
                (position.entry_price * position.size + price * size) / total_size
            )
            position.size = total_size
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                entry_price=price,
                size=size,
                entry_time=timestamp,
                stop_loss=metadata.get("stop_loss"),
                take_profit=metadata.get("take_profit"),
                metadata={"signal_confidence": metadata.get("confidence", 0.0)}
            )
        
        # Record the trade
        self._record_trade(
            symbol=symbol,
            entry_time=timestamp,
            entry_price=price,
            size=size,
            side="buy",
            commission=commission,
            metadata=metadata
        )
    
    async def _exit_position(
        self, symbol: str, price: float, size: float, timestamp: datetime, metadata: Dict[str, Any]
    ) -> None:
        """Exit a position."""
        if symbol not in self.positions:
            logger.warning(f"No position to exit for {symbol}")
            return
            
        position = self.positions[symbol]
        
        # If size is None or larger than position, close the entire position
        if size is None or size > position.size:
            size = position.size
        
        # Calculate P&L and commission
        pnl = (price - position.entry_price) * size
        commission = price * size * self.commission
        
        # Update balance
        self.balance += (price * size - commission)
        
        # Reduce or close position
        if size == position.size:
            del self.positions[symbol]
        else:
            position.size -= size
        
        # Record the trade
        self._record_trade(
            symbol=symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=timestamp,
            exit_price=price,
            size=size,
            side="sell",
            pnl=pnl,
            commission=commission,
            metadata={
                **position.metadata,
                **metadata,
                "exit_reason": metadata.get("exit_reason", "signal")
            }
        )
    
    def _close_position(
        self, position: Position, timestamp: datetime, exit_reason: str
    ) -> None:
        """Close a position due to stop loss, take profit, or end of backtest."""
        if position.symbol not in self.current_prices:
            logger.warning(f"No price available to close position for {position.symbol}")
            return
            
        price = self.current_prices[position.symbol]
        pnl = (price - position.entry_price) * position.size
        commission = price * abs(position.size) * self.commission
        
        # Update balance
        self.balance += (price * position.size - commission)
        
        # Record the trade
        self._record_trade(
            symbol=position.symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=timestamp,
            exit_price=price,
            size=position.size,
            side="sell",
            pnl=pnl,
            commission=commission,
            metadata={
                **position.metadata,
                "exit_reason": exit_reason
            }
        )
        
        # Remove the position
        del self.positions[position.symbol]
    
    def _close_all_positions(self, timestamp: datetime) -> None:
        """Close all open positions at the end of the backtest."""
        for position in list(self.positions.values()):
            self._close_position(position, timestamp, "end_of_backtest")
    
    def _record_trade(
        self,
        symbol: str,
        entry_time: datetime,
        entry_price: float,
        size: float,
        side: str,
        commission: float,
        exit_time: Optional[datetime] = None,
        exit_price: Optional[float] = None,
        pnl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a trade in the trade history."""
        trade = {
            "symbol": symbol,
            "side": side,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "size": size,
            "exit_time": exit_time or entry_time,
            "exit_price": exit_price or entry_price,
            "pnl": pnl or 0.0,
            "commission": commission,
            "net_pnl": (pnl or 0.0) - commission,
            "duration": (exit_time - entry_time).total_seconds() / 3600 if exit_time else 0,
            **metadata or {}
        }
        
        self.trade_history.append(trade)
        self.results.add_trade(trade)
        
        logger.info(
            f"{side.upper()} {symbol}: {size:.6f} @ {entry_price:.2f} "
            f"(P&L: {pnl:.2f}, Commission: {commission:.2f})"
        )
    
    def _get_positions_value(self) -> float:
        """Calculate the total value of all open positions."""
        return sum(
            position.size * self.current_prices.get(position.symbol, 0)
            for position in self.positions.values()
        )
