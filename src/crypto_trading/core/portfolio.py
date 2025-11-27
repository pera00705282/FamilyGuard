"""
Portfolio Management modul za crypto trading bot
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from crypto_trading.utils.config import Config

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Predstavlja trading poziciju"""

    symbol: str
    side: str  # 'buy' ili 'sell'
    amount: float
    avg_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0


@dataclass
class Trade:
    """Predstavlja izvršen trade"""

    symbol: str
    side: str
    amount: float
    price: float
    timestamp: datetime
    pnl: float = 0.0
    fees: float = 0.0


class PortfolioManager:
    """Manager za portfolio tracking i PnL kalkulacije"""

    def __init__(self, config: Config):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.current_prices: Dict[str, float] = {}
        self.initial_balance = 10000.0  # Default $10,000
        self.cash_balance = self.initial_balance
        self.realized_pnl = 0.0

    def get_total_balance(self) -> float:
        """Dobija ukupan balance (cash + pozicije)"""
        position_value = sum(
            pos.amount * self.current_prices.get(pos.symbol, pos.avg_price)
            for pos in self.positions.values()
        )
        return self.cash_balance + position_value

    def get_total_equity(self) -> float:
        """Dobija ukupan equity (balance + unrealized PnL)"""
        return self.get_total_balance() + self.calculate_unrealized_pnl()

    def add_position(self, symbol: str, side: str, amount: float, price: float):
        """Dodaje novu poziciju ili ažurira postojeću"""
        trade_value = amount * price

        if side == "buy":
            self.cash_balance -= trade_value
        else:
            self.cash_balance += trade_value

        # Dodaj trade u istoriju
        trade = Trade(
            symbol=symbol, side=side, amount=amount, price=price, timestamp=datetime.now()
        )
        self.trades.append(trade)

        # Ažuriraj poziciju
        if symbol in self.positions:
            existing_pos = self.positions[symbol]

            if existing_pos.side == side:
                # Dodaj na postojeću poziciju
                total_amount = existing_pos.amount + amount
                total_value = (existing_pos.amount * existing_pos.avg_price) + trade_value
                new_avg_price = total_value / total_amount

                existing_pos.amount = total_amount
                existing_pos.avg_price = new_avg_price
            else:
                # Suprotna pozicija - zatvaranje
                if amount >= existing_pos.amount:
                    # Potpuno zatvaranje + nova pozicija
                    self.close_position(symbol, existing_pos.amount, price)
                    if amount > existing_pos.amount:
                        remaining = amount - existing_pos.amount
                        self.add_position(symbol, side, remaining, price)
                else:
                    # Delimično zatvaranje
                    self.close_position(symbol, amount, price)
        else:
            # Nova pozicija
            self.positions[symbol] = Position(
                symbol=symbol, side=side, amount=amount, avg_price=price, entry_time=datetime.now()
            )

        logger.info(f"Added position: {side} {amount} {symbol} @ {price}")

    def close_position(self, symbol: str, amount: float, price: float):
        """Zatvara poziciju (delimično ili potpuno)"""
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return

        position = self.positions[symbol]

        if amount > position.amount:
            amount = position.amount

        # Kalkuliraj PnL
        if position.side == "buy":
            pnl = amount * (price - position.avg_price)
        else:
            pnl = amount * (position.avg_price - price)

        self.realized_pnl += pnl

        # Ažuriraj cash balance
        if position.side == "buy":
            self.cash_balance += amount * price
        else:
            self.cash_balance -= amount * price

        # Dodaj closing trade
        trade = Trade(
            symbol=symbol,
            side="sell" if position.side == "buy" else "buy",
            amount=amount,
            price=price,
            timestamp=datetime.now(),
            pnl=pnl,
        )
        self.trades.append(trade)

        # Ažuriraj poziciju
        position.amount -= amount

        if position.amount <= 0:
            del self.positions[symbol]

        logger.info(f"Closed position: {amount} {symbol} @ {price}, PnL: ${pnl:.2f}")

    def update_prices(self, prices: Dict[str, float]):
        """Ažurira trenutne cene"""
        self.current_prices.update(prices)

        # Ažuriraj unrealized PnL za sve pozicije
        for symbol, position in self.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                if position.side == "buy":
                    position.unrealized_pnl = position.amount * (current_price - position.avg_price)
                else:
                    position.unrealized_pnl = position.amount * (position.avg_price - current_price)

    def calculate_unrealized_pnl(self) -> float:
        """Kalkuliša ukupan unrealized PnL"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    def get_realized_pnl(self) -> float:
        """Dobija ukupan realized PnL"""
        return self.realized_pnl

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Dobija sve trenutne pozicije"""
        return {
            symbol: {
                "symbol": pos.symbol,
                "side": pos.side,
                "amount": pos.amount,
                "avg_price": pos.avg_price,
                "current_price": self.current_prices.get(symbol, pos.avg_price),
                "unrealized_pnl": pos.unrealized_pnl,
                "entry_time": pos.entry_time,
            }
            for symbol, pos in self.positions.items()
        }

    def get_trades(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Dobija istoriju trade-ova"""
        trades = sorted(self.trades, key=lambda t: t.timestamp, reverse=True)

        if limit:
            trades = trades[:limit]

        return [
            {
                "symbol": trade.symbol,
                "side": trade.side,
                "amount": trade.amount,
                "price": trade.price,
                "timestamp": trade.timestamp,
                "pnl": trade.pnl,
                "fees": trade.fees,
            }
            for trade in trades
        ]

    def get_portfolio_metrics(self) -> Dict[str, Any]:
        """Dobija portfolio performance metrike"""
        total_balance = self.get_total_balance()
        total_equity = self.get_total_equity()
        unrealized_pnl = self.calculate_unrealized_pnl()

        # Kalkuliraj returns
        total_return = ((total_equity - self.initial_balance) / self.initial_balance) * 100

        # Kalkuliraj win rate
        profitable_trades = [t for t in self.trades if t.pnl > 0]
        total_closed_trades = [t for t in self.trades if t.pnl != 0]
        win_rate = (
            (len(profitable_trades) / len(total_closed_trades) * 100) if total_closed_trades else 0
        )

        return {
            "initial_balance": self.initial_balance,
            "cash_balance": self.cash_balance,
            "total_balance": total_balance,
            "total_equity": total_equity,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_return_pct": total_return,
            "active_positions": len(self.positions),
            "total_trades": len(self.trades),
            "win_rate_pct": win_rate,
        }

    def get_daily_pnl(self, days: int = 7) -> List[Dict[str, Any]]:
        """Dobija dnevni PnL za poslednje N dana"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        daily_pnl = []
        current_date = start_date

        while current_date <= end_date:
            day_trades = [
                t for t in self.trades if t.timestamp.date() == current_date.date() and t.pnl != 0
            ]

            day_pnl = sum(t.pnl for t in day_trades)

            daily_pnl.append(
                {"date": current_date.date(), "pnl": day_pnl, "trades": len(day_trades)}
            )

            current_date += timedelta(days=1)

        return daily_pnl

    def reset_portfolio(self):
        """Resetuje portfolio na početno stanje"""
        self.positions.clear()
        self.trades.clear()
        self.current_prices.clear()
        self.cash_balance = self.initial_balance
        self.realized_pnl = 0.0
        logger.info("Portfolio reset to initial state")
