"""
Trading Strategies Module
========================

Implementacija različitih trading strategija za automatsko trgovanje kriptovalutama.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import talib

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Trading signal"""

    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    strength: float  # 0.0 - 1.0
    price: float
    timestamp: datetime
    strategy: str
    metadata: Dict[str, Any] = None


@dataclass
class MarketData:
    """Market data struktura"""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class BaseStrategy(ABC):
    """Bazna klasa za sve strategije"""

    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self.data_buffer: Dict[str, List[MarketData]] = {}
        self.signals: List[Signal] = []

    @abstractmethod
    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira podatke i generiše signal"""

    def add_data(self, symbol: str, data: MarketData):
        """Dodaje nove podatke u buffer"""
        if symbol not in self.data_buffer:
            self.data_buffer[symbol] = []

        self.data_buffer[symbol].append(data)

        # Čuva samo poslednje N podataka
        max_buffer_size = self.params.get("buffer_size", 1000)
        if len(self.data_buffer[symbol]) > max_buffer_size:
            self.data_buffer[symbol] = self.data_buffer[symbol][-max_buffer_size:]

    def get_dataframe(self, symbol: str, periods: int = None) -> pd.DataFrame:
        """Konvertuje podatke u pandas DataFrame"""
        if symbol not in self.data_buffer or not self.data_buffer[symbol]:
            return pd.DataFrame()

        data = self.data_buffer[symbol]
        if periods:
            data = data[-periods:]

        df = pd.DataFrame(
            [
                {
                    "timestamp": d.timestamp,
                    "open": d.open,
                    "high": d.high,
                    "low": d.low,
                    "close": d.close,
                    "volume": d.volume,
                }
                for d in data
            ]
        )

        df.set_index("timestamp", inplace=True)
        return df


class MovingAverageCrossStrategy(BaseStrategy):
    """Moving Average Crossover strategija"""

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__(
            "MA_Cross",
            {
                "fast_period": fast_period,
                "slow_period": slow_period,
                "buffer_size": max(fast_period, slow_period) * 3,
            },
        )

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira MA crossover"""
        df = self.get_dataframe(symbol)

        if len(df) < self.params["slow_period"]:
            return None

        # Računanje moving averages
        fast_ma = df["close"].rolling(window=self.params["fast_period"]).mean()
        slow_ma = df["close"].rolling(window=self.params["slow_period"]).mean()

        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return None

        # Provera crossover-a
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]

        current_price = df["close"].iloc[-1]

        # Bullish crossover
        if prev_fast <= prev_slow and current_fast > current_slow:
            return Signal(
                symbol=symbol,
                action="buy",
                strength=0.7,
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "fast_ma": current_fast,
                    "slow_ma": current_slow,
                    "crossover_type": "bullish",
                },
            )

        # Bearish crossover
        elif prev_fast >= prev_slow and current_fast < current_slow:
            return Signal(
                symbol=symbol,
                action="sell",
                strength=0.7,
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "fast_ma": current_fast,
                    "slow_ma": current_slow,
                    "crossover_type": "bearish",
                },
            )

        return None


class RSIStrategy(BaseStrategy):
    """RSI (Relative Strength Index) strategija"""

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        super().__init__(
            "RSI",
            {
                "period": period,
                "oversold": oversold,
                "overbought": overbought,
                "buffer_size": period * 3,
            },
        )

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira RSI signale"""
        df = self.get_dataframe(symbol)

        if len(df) < self.params["period"] + 1:
            return None

        # Računanje RSI
        closes = df["close"].values
        rsi = talib.RSI(closes, timeperiod=self.params["period"])

        if len(rsi) < 2:
            return None

        current_rsi = rsi[-1]
        prev_rsi = rsi[-2]
        current_price = df["close"].iloc[-1]

        # Oversold -> Buy signal
        if prev_rsi <= self.params["oversold"] and current_rsi > self.params["oversold"]:
            return Signal(
                symbol=symbol,
                action="buy",
                strength=min(1.0, (self.params["oversold"] - prev_rsi) / 10),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={"rsi": current_rsi, "condition": "oversold_recovery"},
            )

        # Overbought -> Sell signal
        elif prev_rsi >= self.params["overbought"] and current_rsi < self.params["overbought"]:
            return Signal(
                symbol=symbol,
                action="sell",
                strength=min(1.0, (prev_rsi - self.params["overbought"]) / 10),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={"rsi": current_rsi, "condition": "overbought_decline"},
            )

        return None


class MACDStrategy(BaseStrategy):
    """MACD (Moving Average Convergence Divergence) strategija"""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        super().__init__(
            "MACD",
            {
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period,
                "buffer_size": slow_period + signal_period + 10,
            },
        )

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira MACD signale"""
        df = self.get_dataframe(symbol)

        required_periods = self.params["slow_period"] + self.params["signal_period"]
        if len(df) < required_periods:
            return None

        # Računanje MACD
        closes = df["close"].values
        macd, macd_signal, macd_hist = talib.MACD(
            closes,
            fastperiod=self.params["fast_period"],
            slowperiod=self.params["slow_period"],
            signalperiod=self.params["signal_period"],
        )

        if len(macd_hist) < 2:
            return None

        current_hist = macd_hist[-1]
        prev_hist = macd_hist[-2]
        current_price = df["close"].iloc[-1]

        # Bullish crossover (histogram crosses above zero)
        if prev_hist <= 0 and current_hist > 0:
            return Signal(
                symbol=symbol,
                action="buy",
                strength=min(1.0, abs(current_hist) * 10),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "macd": macd[-1],
                    "signal": macd_signal[-1],
                    "histogram": current_hist,
                    "crossover_type": "bullish",
                },
            )

        # Bearish crossover (histogram crosses below zero)
        elif prev_hist >= 0 and current_hist < 0:
            return Signal(
                symbol=symbol,
                action="sell",
                strength=min(1.0, abs(current_hist) * 10),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "macd": macd[-1],
                    "signal": macd_signal[-1],
                    "histogram": current_hist,
                    "crossover_type": "bearish",
                },
            )

        return None


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands strategija"""

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__(
            "BollingerBands", {"period": period, "std_dev": std_dev, "buffer_size": period * 2}
        )

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira Bollinger Bands signale"""
        df = self.get_dataframe(symbol)

        if len(df) < self.params["period"]:
            return None

        # Računanje Bollinger Bands
        closes = df["close"].values
        upper, middle, lower = talib.BBANDS(
            closes,
            timeperiod=self.params["period"],
            nbdevup=self.params["std_dev"],
            nbdevdn=self.params["std_dev"],
        )

        if len(upper) < 2:
            return None

        current_price = closes[-1]
        prev_price = closes[-2]
        current_upper = upper[-1]
        current_lower = lower[-1]
        current_middle = middle[-1]

        # Bounce off lower band (buy signal)
        if prev_price <= lower[-2] and current_price > current_lower:
            distance_from_middle = abs(current_price - current_middle) / current_middle
            return Signal(
                symbol=symbol,
                action="buy",
                strength=min(1.0, distance_from_middle * 5),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "upper_band": current_upper,
                    "middle_band": current_middle,
                    "lower_band": current_lower,
                    "band_position": "lower_bounce",
                },
            )

        # Bounce off upper band (sell signal)
        elif prev_price >= upper[-2] and current_price < current_upper:
            distance_from_middle = abs(current_price - current_middle) / current_middle
            return Signal(
                symbol=symbol,
                action="sell",
                strength=min(1.0, distance_from_middle * 5),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "upper_band": current_upper,
                    "middle_band": current_middle,
                    "lower_band": current_lower,
                    "band_position": "upper_bounce",
                },
            )

        return None


class VolumeWeightedStrategy(BaseStrategy):
    """Volume Weighted strategija"""

    def __init__(self, period: int = 20, volume_threshold: float = 1.5):
        super().__init__(
            "VolumeWeighted",
            {"period": period, "volume_threshold": volume_threshold, "buffer_size": period * 2},
        )

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira volume-based signale"""
        df = self.get_dataframe(symbol)

        if len(df) < self.params["period"]:
            return None

        # Računanje prosečnog volumena
        avg_volume = df["volume"].rolling(window=self.params["period"]).mean()

        if len(avg_volume) < 2:
            return None

        current_volume = df["volume"].iloc[-1]
        current_avg_volume = avg_volume.iloc[-1]
        current_price = df["close"].iloc[-1]
        prev_price = df["close"].iloc[-2]

        # Visok volume + rast cene = buy signal
        if (
            current_volume > current_avg_volume * self.params["volume_threshold"]
            and current_price > prev_price
        ):

            volume_ratio = current_volume / current_avg_volume
            price_change = (current_price - prev_price) / prev_price

            return Signal(
                symbol=symbol,
                action="buy",
                strength=min(1.0, volume_ratio * price_change * 10),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "volume_ratio": volume_ratio,
                    "price_change": price_change,
                    "avg_volume": current_avg_volume,
                },
            )

        # Visok volume + pad cene = sell signal
        elif (
            current_volume > current_avg_volume * self.params["volume_threshold"]
            and current_price < prev_price
        ):

            volume_ratio = current_volume / current_avg_volume
            price_change = abs(current_price - prev_price) / prev_price

            return Signal(
                symbol=symbol,
                action="sell",
                strength=min(1.0, volume_ratio * price_change * 10),
                price=current_price,
                timestamp=df.index[-1],
                strategy=self.name,
                metadata={
                    "volume_ratio": volume_ratio,
                    "price_change": -price_change,
                    "avg_volume": current_avg_volume,
                },
            )

        return None


class MultiStrategyManager:
    """Manager za kombinovanje više strategija"""

    def __init__(self, strategies: List[BaseStrategy] = None, weights: Dict[str, float] = None):
        self.strategies = strategies or []
        self.weights = weights or {}

    def add_strategy(self, strategy: BaseStrategy, weight: float = 1.0):
        """Dodaje strategiju u manager"""
        self.strategies.append(strategy)
        self.weights[strategy.name] = weight

    async def analyze_all(self, symbol: str, data: List[MarketData]) -> List[Signal]:
        """Analizira sve strategije"""
        signals = []

        for strategy in self.strategies:
            # Dodaj podatke u strategiju
            for d in data:
                strategy.add_data(symbol, d)

            # Generiši signal
            signal = await strategy.analyze(symbol, data)
            if signal:
                # Primeni težinu
                signal.strength *= self.weights.get(strategy.name, 1.0)
                signals.append(signal)

        return signals

    def combine_signals(self, signals: List[Signal]) -> Optional[Signal]:
        """Kombinuje signale u jedan finalni signal"""
        if not signals:
            return None

        # Grupiši po akciji
        buy_signals = [s for s in signals if s.action == "buy"]
        sell_signals = [s for s in signals if s.action == "sell"]

        buy_strength = sum(s.strength for s in buy_signals)
        sell_strength = sum(s.strength for s in sell_signals)

        # Određi finalnu akciju
        if buy_strength > sell_strength and buy_strength > 0.5:
            return Signal(
                symbol=signals[0].symbol,
                action="buy",
                strength=min(1.0, buy_strength),
                price=signals[0].price,
                timestamp=signals[0].timestamp,
                strategy="MultiStrategy",
                metadata={
                    "buy_signals": len(buy_signals),
                    "sell_signals": len(sell_signals),
                    "buy_strength": buy_strength,
                    "sell_strength": sell_strength,
                    "strategies": [s.strategy for s in buy_signals],
                },
            )
        elif sell_strength > buy_strength and sell_strength > 0.5:
            return Signal(
                symbol=signals[0].symbol,
                action="sell",
                strength=min(1.0, sell_strength),
                price=signals[0].price,
                timestamp=signals[0].timestamp,
                strategy="MultiStrategy",
                metadata={
                    "buy_signals": len(buy_signals),
                    "sell_signals": len(sell_signals),
                    "buy_strength": buy_strength,
                    "sell_strength": sell_strength,
                    "strategies": [s.strategy for s in sell_signals],
                },
            )

        return None

    async def get_combined_signals(self, symbol: str) -> List[Signal]:
        """Dobija kombinovane signale za simbol"""
        if not self.strategies:
            return []

        # Uzmi podatke iz prve strategije
        if symbol not in self.strategies[0].data_buffer:
            return []

        data = self.strategies[0].data_buffer[symbol]
        if not data:
            return []

        # Analiziraj sve strategije
        all_signals = await self.analyze_all(symbol, data)

        # Kombiniraj signale
        combined_signal = self.combine_signals(all_signals)

        return [combined_signal] if combined_signal else []

    def get_strategy_performance(self) -> Dict[str, Dict[str, Any]]:
        """Dobija performance metrike za sve strategije"""
        performance = {}

        for strategy in self.strategies:
            performance[strategy.name] = {
                "total_signals": len(strategy.signals),
                "parameters": strategy.params,
                "data_points": sum(len(data) for data in strategy.data_buffer.values()),
            }

        return performance


# Predefinisane kombinacije strategija
def create_conservative_strategy() -> MultiStrategyManager:
    """Kreira konzervativnu strategiju"""
    strategies = [
        MovingAverageCrossStrategy(fast_period=20, slow_period=50),
        RSIStrategy(period=14, oversold=25, overbought=75),
        BollingerBandsStrategy(period=20, std_dev=2.0),
    ]

    weights = {"MA_Cross": 0.4, "RSI": 0.3, "BollingerBands": 0.3}

    return MultiStrategyManager(strategies, weights)


def create_aggressive_strategy() -> MultiStrategyManager:
    """Kreira agresivnu strategiju"""
    strategies = [
        MovingAverageCrossStrategy(fast_period=5, slow_period=15),
        RSIStrategy(period=7, oversold=35, overbought=65),
        MACDStrategy(fast_period=8, slow_period=21, signal_period=5),
        VolumeWeightedStrategy(period=10, volume_threshold=2.0),
    ]

    weights = {"MA_Cross": 0.25, "RSI": 0.25, "MACD": 0.25, "VolumeWeighted": 0.25}

    return MultiStrategyManager(strategies, weights)


def create_scalping_strategy() -> MultiStrategyManager:
    """Kreira scalping strategiju"""
    strategies = [
        MovingAverageCrossStrategy(fast_period=3, slow_period=8),
        RSIStrategy(period=5, oversold=40, overbought=60),
        VolumeWeightedStrategy(period=5, volume_threshold=3.0),
    ]

    weights = {"MA_Cross": 0.4, "RSI": 0.3, "VolumeWeighted": 0.3}

    return MultiStrategyManager(strategies, weights)
