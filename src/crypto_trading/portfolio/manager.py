"""
Portfolio Management Module
===========================

Upravljanje portfoliom, pozicijama i risk management-om.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json
from enum import Enum

logger = logging.getLogger(__name__)


class PositionType(Enum):
    LONG = "long"
    SHORT = "short"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Position:
    """Trading pozicija"""

    symbol: str
    side: PositionType
    size: float
    entry_price: float
    current_price: float
    timestamp: datetime
    exchange: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def update_price(self, new_price: float):
        """Ažurira trenutnu cenu i PnL"""
        self.current_price = new_price

        if self.side == PositionType.LONG:
            self.unrealized_pnl = (new_price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - new_price) * self.size

    def get_pnl_percentage(self) -> float:
        """Vraća PnL u procentima"""
        if self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.size)) * 100


@dataclass
class Order:
    """Trading order"""

    id: str
    symbol: str
    side: str  # 'buy' ili 'sell'
    type: str  # 'market', 'limit', 'stop'
    amount: float
    price: Optional[float]
    status: OrderStatus
    timestamp: datetime
    exchange: str
    filled: float = 0.0
    remaining: float = 0.0
    cost: float = 0.0
    fee: float = 0.0


@dataclass
class Balance:
    """Balance za određenu valutu"""

    currency: str
    free: float
    used: float
    total: float

    @property
    def available(self) -> float:
        """Dostupan iznos za trgovanje"""
        return self.free


@dataclass
class Trade:
    """Izvršen trade"""

    id: str
    order_id: str
    symbol: str
    side: str
    amount: float
    price: float
    cost: float
    fee: float
    timestamp: datetime
    exchange: str


class PortfolioManager:
    """Glavni portfolio manager"""

    def __init__(self, initial_balance: float = 10000.0, base_currency: str = "USDT"):
        self.base_currency = base_currency
        self.initial_balance = initial_balance
        self.balances: Dict[str, Balance] = {
            base_currency: Balance(base_currency, initial_balance, 0.0, initial_balance)
        }
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = initial_balance

    def get_total_balance(self, prices: Dict[str, float] = None) -> float:
        """Računa ukupan balance u base valuti"""
        total = 0.0
        prices = prices or {}

        for currency, balance in self.balances.items():
            if currency == self.base_currency:
                total += balance.total
            else:
                # Konvertuj u base valutu
                price_key = f"{currency}/{self.base_currency}"
                if price_key in prices:
                    total += balance.total * prices[price_key]

        # Dodaj unrealized PnL iz pozicija
        for position in self.positions.values():
            total += position.unrealized_pnl

        return total

    def get_available_balance(self, currency: str = None) -> float:
        """Vraća dostupan balance"""
        currency = currency or self.base_currency
        if currency in self.balances:
            return self.balances[currency].available
        return 0.0

    def calculate_position_size(
        self, symbol: str, price: float, risk_amount: float, stop_loss_pct: float
    ) -> float:
        """Računa veličinu pozicije na osnovu rizika"""
        available_balance = self.get_available_balance()

        # Maksimalna vrednost pozicije na osnovu dostupnog balansa
        max_position_value = available_balance * 0.95  # Ostavi 5% za fees

        # Pozicija na osnovu rizika
        if stop_loss_pct > 0:
            risk_position_value = risk_amount / stop_loss_pct
            position_value = min(max_position_value, risk_position_value)
        else:
            position_value = max_position_value * 0.1  # Konzervativno 10%

        return position_value / price

    def can_open_position(self, symbol: str, side: str, size: float, price: float) -> bool:
        """Proverava da li se pozicija može otvoriti"""
        required_balance = size * price * 1.01  # +1% za fees
        available = self.get_available_balance()

        if required_balance > available:
            logger.warning(
                f"Insufficient balance: required {required_balance}, available {available}"
            )
            return False

        # Proveri da li već postoji pozicija za ovaj simbol
        if symbol in self.positions:
            logger.warning(f"Position already exists for {symbol}")
            return False

        return True

    def open_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        exchange: str,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> bool:
        """Otvara novu poziciju"""
        if not self.can_open_position(symbol, side, size, entry_price):
            return False

        position_type = PositionType.LONG if side == "buy" else PositionType.SHORT

        position = Position(
            symbol=symbol,
            side=position_type,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            timestamp=datetime.now(),
            exchange=exchange,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.positions[symbol] = position

        # Ažuriraj balance
        cost = size * entry_price
        base_balance = self.balances[self.base_currency]
        base_balance.free -= cost
        base_balance.used += cost

        logger.info(f"Opened {side} position for {symbol}: {size} @ {entry_price}")
        return True

    def close_position(self, symbol: str, exit_price: float) -> Optional[float]:
        """Zatvara poziciju"""
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return None

        position = self.positions[symbol]
        position.update_price(exit_price)

        # Realizuj PnL
        realized_pnl = position.unrealized_pnl
        self.total_pnl += realized_pnl

        # Ažuriraj balance
        cost = position.size * position.entry_price
        proceeds = position.size * exit_price

        base_balance = self.balances[self.base_currency]
        base_balance.used -= cost
        base_balance.free += proceeds
        base_balance.total = base_balance.free + base_balance.used

        # Ukloni poziciju
        del self.positions[symbol]

        logger.info(f"Closed position for {symbol}: PnL = {realized_pnl:.2f}")
        return realized_pnl

    def update_position_prices(self, prices: Dict[str, float]):
        """Ažurira cene za sve pozicije"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])

    def check_stop_loss_take_profit(self, prices: Dict[str, float]) -> List[str]:
        """Proverava stop loss i take profit nivoe"""
        to_close = []

        for symbol, position in self.positions.items():
            if symbol not in prices:
                continue

            current_price = prices[symbol]

            # Stop Loss
            if position.stop_loss:
                if (position.side == PositionType.LONG and current_price <= position.stop_loss) or (
                    position.side == PositionType.SHORT and current_price >= position.stop_loss
                ):
                    logger.info(f"Stop loss triggered for {symbol} at {current_price}")
                    to_close.append(symbol)
                    continue

            # Take Profit
            if position.take_profit:
                if (
                    position.side == PositionType.LONG and current_price >= position.take_profit
                ) or (
                    position.side == PositionType.SHORT and current_price <= position.take_profit
                ):
                    logger.info(f"Take profit triggered for {symbol} at {current_price}")
                    to_close.append(symbol)

        return to_close

    def calculate_drawdown(self) -> float:
        """Računa trenutni drawdown"""
        current_balance = self.get_total_balance()

        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        if self.peak_balance > 0:
            drawdown = (self.peak_balance - current_balance) / self.peak_balance
            self.max_drawdown = max(self.max_drawdown, drawdown)
            return drawdown

        return 0.0

    def get_portfolio_summary(self, prices: Dict[str, float] = None) -> Dict[str, Any]:
        """Vraća sažetak portfolia"""
        total_balance = self.get_total_balance(prices)
        drawdown = self.calculate_drawdown()

        # Pozicije
        positions_summary = []
        total_unrealized_pnl = 0.0

        for symbol, position in self.positions.items():
            pnl_pct = position.get_pnl_percentage()
            total_unrealized_pnl += position.unrealized_pnl

            positions_summary.append(
                {
                    "symbol": symbol,
                    "side": position.side.value,
                    "size": position.size,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "unrealized_pnl": position.unrealized_pnl,
                    "pnl_percentage": pnl_pct,
                    "stop_loss": position.stop_loss,
                    "take_profit": position.take_profit,
                }
            )

        return {
            "total_balance": total_balance,
            "initial_balance": self.initial_balance,
            "total_pnl": self.total_pnl,
            "unrealized_pnl": total_unrealized_pnl,
            "total_return_pct": ((total_balance - self.initial_balance) / self.initial_balance)
            * 100,
            "max_drawdown": self.max_drawdown * 100,
            "current_drawdown": drawdown * 100,
            "open_positions": len(self.positions),
            "positions": positions_summary,
            "balances": {
                curr: {"free": bal.free, "used": bal.used, "total": bal.total}
                for curr, bal in self.balances.items()
            },
        }

    def get_performance_metrics(self) -> Dict[str, float]:
        """Računa performance metrike"""
        if not self.trades:
            return {}

        # Winning/Losing trades
        winning_trades = [t for t in self.trades if t.cost > 0]  # Simplified
        losing_trades = [t for t in self.trades if t.cost < 0]  # Simplified

        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        # Average win/loss
        avg_win = sum(t.cost for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.cost for t in losing_trades) / len(losing_trades) if losing_trades else 0

        # Profit factor
        total_wins = sum(t.cost for t in winning_trades)
        total_losses = abs(sum(t.cost for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate * 100,
            "average_win": avg_win,
            "average_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": self.max_drawdown * 100,
        }

    def save_state(self, filename: str):
        """Čuva stanje portfolia"""
        state = {
            "balances": {
                curr: {
                    "currency": bal.currency,
                    "free": bal.free,
                    "used": bal.used,
                    "total": bal.total,
                }
                for curr, bal in self.balances.items()
            },
            "positions": {
                symbol: {
                    "symbol": pos.symbol,
                    "side": pos.side.value,
                    "size": pos.size,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "timestamp": pos.timestamp.isoformat(),
                    "exchange": pos.exchange,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for symbol, pos in self.positions.items()
            },
            "trades": [
                {
                    "id": trade.id,
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "amount": trade.amount,
                    "price": trade.price,
                    "cost": trade.cost,
                    "fee": trade.fee,
                    "timestamp": trade.timestamp.isoformat(),
                    "exchange": trade.exchange,
                }
                for trade in self.trades
            ],
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "peak_balance": self.peak_balance,
            "initial_balance": self.initial_balance,
        }

        with open(filename, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self, filename: str):
        """Učitava stanje portfolia"""
        try:
            with open(filename, "r") as f:
                state = json.load(f)

            # Učitaj balanse
            self.balances = {}
            for curr, bal_data in state["balances"].items():
                self.balances[curr] = Balance(**bal_data)

            # Učitaj pozicije
            self.positions = {}
            for symbol, pos_data in state["positions"].items():
                pos_data["side"] = PositionType(pos_data["side"])
                pos_data["timestamp"] = datetime.fromisoformat(pos_data["timestamp"])
                self.positions[symbol] = Position(**pos_data)

            # Učitaj trades
            self.trades = []
            for trade_data in state["trades"]:
                trade_data["timestamp"] = datetime.fromisoformat(trade_data["timestamp"])
                self.trades.append(Trade(**trade_data))

            # Ostale vrednosti
            self.total_pnl = state["total_pnl"]
            self.max_drawdown = state["max_drawdown"]
            self.peak_balance = state["peak_balance"]
            self.initial_balance = state["initial_balance"]

            logger.info(f"Portfolio state loaded from {filename}")

        except Exception as e:
            logger.error(f"Failed to load portfolio state: {e}")


class RiskManager:
    """Napredni risk management"""

    def __init__(
        self,
        max_risk_per_trade: float = 0.02,
        max_portfolio_risk: float = 0.1,
        max_correlation: float = 0.7,
        max_drawdown: float = 0.15,
    ):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_portfolio_risk = max_portfolio_risk
        self.max_correlation = max_correlation
        self.max_drawdown = max_drawdown
        self.correlation_matrix: Dict[Tuple[str, str], float] = {}

    def calculate_portfolio_risk(
        self, portfolio: PortfolioManager, volatilities: Dict[str, float]
    ) -> float:
        """Računa ukupan portfolio rizik"""
        total_risk = 0.0

        for symbol, position in portfolio.positions.items():
            if symbol in volatilities:
                position_value = position.size * position.current_price
                position_risk = position_value * volatilities[symbol]
                total_risk += position_risk**2

        return (total_risk**0.5) / portfolio.get_total_balance()

    def check_correlation_risk(self, new_symbol: str, portfolio: PortfolioManager) -> bool:
        """Proverava korelacijski rizik"""
        for existing_symbol in portfolio.positions.keys():
            correlation_key = tuple(sorted([new_symbol, existing_symbol]))
            correlation = self.correlation_matrix.get(correlation_key, 0.0)

            if abs(correlation) > self.max_correlation:
                logger.warning(
                    f"High correlation between {new_symbol} and {existing_symbol}: {correlation}"
                )
                return False

        return True

    def validate_trade(
        self,
        portfolio: PortfolioManager,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: float = None,
    ) -> Tuple[bool, str]:
        """Validira trade na osnovu risk management pravila"""

        # 1. Proveri drawdown
        current_drawdown = portfolio.calculate_drawdown()
        if current_drawdown > self.max_drawdown:
            return False, f"Maximum drawdown exceeded: {current_drawdown:.2%}"

        # 2. Proveri rizik po trade-u
        if stop_loss:
            risk_amount = abs(price - stop_loss) * size
            portfolio_value = portfolio.get_total_balance()
            risk_percentage = risk_amount / portfolio_value

            if risk_percentage > self.max_risk_per_trade:
                return False, f"Risk per trade too high: {risk_percentage:.2%}"

        # 3. Proveri korelaciju
        if not self.check_correlation_risk(symbol, portfolio):
            return False, "High correlation risk detected"

        # 4. Proveri koncentraciju
        position_value = size * price
        portfolio_value = portfolio.get_total_balance()
        concentration = position_value / portfolio_value

        if concentration > 0.2:  # Maksimalno 20% portfolia u jednoj poziciji
            return False, f"Position concentration too high: {concentration:.2%}"

        return True, "Trade approved"

    def update_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """Ažurira korelaciju između simbola"""
        key = tuple(sorted([symbol1, symbol2]))
        self.correlation_matrix[key] = correlation

    def calculate_optimal_position_size(
        self,
        portfolio: PortfolioManager,
        symbol: str,
        price: float,
        volatility: float,
        stop_loss_pct: float,
    ) -> float:
        """Računa optimalnu veličinu pozicije koristeći Kelly Criterion"""
        portfolio_value = portfolio.get_total_balance()

        # Kelly Criterion: f = (bp - q) / b
        # Gde je: b = odds, p = verovatnoća pobede, q = verovatnoća gubitka
        # Simplifikovano za crypto trading

        win_rate = 0.55  # Pretpostavka 55% win rate
        avg_win = 0.03  # Prosečan dobitak 3%
        avg_loss = stop_loss_pct  # Prosečan gubitak = stop loss

        if avg_loss == 0:
            return 0

        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_loss
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Ograniči na 25%

        # Ograniči na maksimalni rizik po trade-u
        max_position_value = portfolio_value * self.max_risk_per_trade / stop_loss_pct
        kelly_position_value = portfolio_value * kelly_fraction

        optimal_position_value = min(max_position_value, kelly_position_value)
        return optimal_position_value / price
