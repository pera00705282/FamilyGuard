#!/usr/bin/env python3
"""

    from crypto_trading.strategies import MultiStrategyManager, MovingAverageCrossStrategy


Custom Strategy Example
======================

Primer kreiranja custom trading strategije.
"""

from typing import List, Optional

# Dodaj src direktorijum u Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


console = Console()

class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy

    Strategija koja trguje na osnovu vraćanja cene ka srednjoj vrednosti.
    Koristi Bollinger Bands i RSI za identifikaciju overbought/oversold uslova.
    """

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0, rsi_period: int = 14):
        super().__init__()
        self.name = "MeanReversion"
        self.params = {
            'bb_period': bb_period,
            'bb_std': bb_std,
            'rsi_period': rsi_period
        }

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira podatke i generiše signal"""

        if len(data) < max(self.params['bb_period'], self.params['rsi_period']):
            return None

        # Konvertuj u DataFrame
        df = self.get_dataframe(symbol)
        if len(df) < max(self.params['bb_period'], self.params['rsi_period']):
            return None

        # Izračunaj Bollinger Bands
        bb_period = self.params['bb_period']
        bb_std = self.params['bb_std']

        df['sma'] = df['close'].rolling(window=bb_period).mean()
        df['std'] = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['sma'] + (df['std'] * bb_std)
        df['bb_lower'] = df['sma'] - (df['std'] * bb_std)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # Izračunaj RSI
        rsi_period = self.params['rsi_period']
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Trenutne vrednosti
        current_price = df['close'].iloc[-1]
        current_bb_pos = df['bb_position'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]

        # Signal logika
        signal_action = None
        signal_strength = 0.0

        # Buy signal: cena blizu donje BB linije i RSI oversold
        if current_bb_pos < 0.2 and current_rsi < 30:
            signal_action = "buy"
            signal_strength = min(1.0, (30 - current_rsi) / 30 + (0.2 - current_bb_pos) / 0.2) / 2

        # Sell signal: cena blizu gornje BB linije i RSI overbought
        elif current_bb_pos > 0.8 and current_rsi > 70:
            signal_action = "sell"
            signal_strength = min(1.0, (current_rsi - 70) / 30 + (current_bb_pos - 0.8) / 0.2) / 2

        if signal_action:
            return Signal(
                symbol=symbol,
                action=signal_action,
                strength=signal_strength,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                metadata={
                    'bb_position': current_bb_pos,
                    'rsi': current_rsi,
                    'bb_upper': df['bb_upper'].iloc[-1],
                    'bb_lower': df['bb_lower'].iloc[-1],
                    'sma': df['sma'].iloc[-1]
                }
            )

        return None

class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy

    Strategija koja trguje na proboj ključnih nivoa podrške/otpora.
    Koristi volume za potvrdu breakout-a.
    """

    def __init__(self, lookback_period: int = 20, volume_threshold: float = 1.5):
        super().__init__()
        self.name = "Breakout"
        self.params = {
            'lookback_period': lookback_period,
            'volume_threshold': volume_threshold
        }

    async def analyze(self, symbol: str, data: List[MarketData]) -> Optional[Signal]:
        """Analizira podatke i generiše signal"""

        lookback = self.params['lookback_period']
        if len(data) < lookback + 5:
            return None

        df = self.get_dataframe(symbol)
        if len(df) < lookback + 5:
            return None

        # Izračunaj support/resistance nivoe
        df['high_max'] = df['high'].rolling(window=lookback).max()
        df['low_min'] = df['low'].rolling(window=lookback).min()

        # Volume analiza
        df['volume_sma'] = df['volume'].rolling(window=lookback).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']

        # Trenutne vrednosti
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_volume_ratio = df['volume_ratio'].iloc[-1]

        resistance = df['high_max'].iloc[-2]  # Prethodna vrednost
        support = df['low_min'].iloc[-2]      # Prethodna vrednost

        # Signal logika
        signal_action = None
        signal_strength = 0.0

        # Bullish breakout: proboj otpora sa visokim volume-om
        if (current_high > resistance and
            current_price > resistance and
            current_volume_ratio > self.params['volume_threshold']):

            signal_action = "buy"
            breakout_strength = min(1.0, (current_price - resistance) / resistance * 100)
            volume_strength = min(1.0, current_volume_ratio / self.params['volume_threshold'] - 1)
            signal_strength = (breakout_strength + volume_strength) / 2

        # Bearish breakout: proboj podrške sa visokim volume-om
        elif (current_low < support and
              current_price < support and
              current_volume_ratio > self.params['volume_threshold']):

            signal_action = "sell"
            breakout_strength = min(1.0, (support - current_price) / support * 100)
            volume_strength = min(1.0, current_volume_ratio / self.params['volume_threshold'] - 1)
            signal_strength = (breakout_strength + volume_strength) / 2

        if signal_action:
            return Signal(
                symbol=symbol,
                action=signal_action,
                strength=signal_strength,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                metadata={
                    'resistance': resistance,
                    'support': support,
                    'volume_ratio': current_volume_ratio,
                    'breakout_level': resistance if signal_action == "buy" else support
                }
            )

        return None

async def test_custom_strategies():
    """Testira custom strategije"""

    console.print("[bold blue]🧪 Testing Custom Strategies[/bold blue]")

    # Kreiranje strategija
    mean_reversion = MeanReversionStrategy(bb_period=20, bb_std=2.0, rsi_period=14)
    breakout = BreakoutStrategy(lookback_period=20, volume_threshold=1.5)

    console.print("✅ Kreiran MeanReversionStrategy i BreakoutStrategy")

    # Generisanje test podataka
    console.print("📊 Generisanje test podataka...")

    # Simulacija mean reversion scenario
    mr_data = []
    base_price = 50000.0

    # Trend up pa down (mean reversion pattern)
    for i in range(50):
        if i < 20:
            price_change = np.random.normal(0.005, 0.01)  # Trend up
        elif i < 30:
            price_change = np.random.normal(-0.008, 0.015)  # Sharp down (oversold)
        else:
            price_change = np.random.normal(0.003, 0.008)  # Recovery

        base_price *= (1 + price_change)
        volume = np.random.uniform(800, 1200)

        market_data = MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            open=base_price * 0.999,
            high=base_price * 1.002,
            low=base_price * 0.998,
            close=base_price,
            volume=volume
        )

        mean_reversion.add_data("BTC/USDT", market_data)
        mr_data.append(market_data)

    # Test Mean Reversion Strategy
    console.print("\n🎯 Testing Mean Reversion Strategy...")
    mr_signal = await mean_reversion.analyze("BTC/USDT", mr_data[-10:])

    if mr_signal:
        console.print(f"✅ Signal: {mr_signal.action.upper()} {mr_signal.symbol}")
        console.print(f"   Snaga: {mr_signal.strength:.3f}")
        console.print(f"   RSI: {mr_signal.metadata.get('rsi', 0):.1f}")
        console.print(f"   BB Position: {mr_signal.metadata.get('bb_position', 0):.3f}")
    else:
        console.print("⚪ Nema signala za Mean Reversion")

    # Simulacija breakout scenario
    bo_data = []
    base_price = 45000.0

    # Konsolidacija pa breakout
    for i in range(50):
        if i < 30:
            # Konsolidacija (sideways)
            price_change = np.random.normal(0, 0.005)
            volume = np.random.uniform(500, 800)  # Nizak volume
        else:
            # Breakout sa visokim volume-om
            price_change = np.random.normal(0.015, 0.005)  # Strong uptrend
            volume = np.random.uniform(1500, 2500)  # Visok volume

        base_price *= (1 + price_change)

        market_data = MarketData(
            symbol="ETH/USDT",
            timestamp=datetime.now(),
            open=base_price * 0.999,
            high=base_price * 1.003,
            low=base_price * 0.997,
            close=base_price,
            volume=volume
        )

        breakout.add_data("ETH/USDT", market_data)
        bo_data.append(market_data)

    # Test Breakout Strategy
    console.print("\n🚀 Testing Breakout Strategy...")
    bo_signal = await breakout.analyze("ETH/USDT", bo_data[-10:])

    if bo_signal:
        console.print(f"✅ Signal: {bo_signal.action.upper()} {bo_signal.symbol}")
        console.print(f"   Snaga: {bo_signal.strength:.3f}")
        console.print(f"   Volume Ratio: {bo_signal.metadata.get('volume_ratio', 0):.2f}")
        console.print(f"   Breakout Level: ${bo_signal.metadata.get('breakout_level', 0):.2f}")
    else:
        console.print("⚪ Nema signala za Breakout")

async def combine_custom_strategies():
    """Kombinuje custom strategije sa postojećima"""

    console.print("\n[bold green]🔗 Combining Custom Strategies[/bold green]")


    # Kreiranje strategija
    ma_strategy = MovingAverageCrossStrategy(fast_period=10, slow_period=30)
    mr_strategy = MeanReversionStrategy()
    bo_strategy = BreakoutStrategy()

    # Multi-strategy manager
    strategies = [ma_strategy, mr_strategy, bo_strategy]
    weights = {
        'MA_Cross': 0.4,
        'MeanReversion': 0.3,
        'Breakout': 0.3
    }

    multi_manager = MultiStrategyManager(strategies, weights)

    console.print("✅ Kreiran MultiStrategyManager sa 3 strategije:")
    console.print("   - Moving Average Cross (40%)")
    console.print("   - Mean Reversion (30%)")
    console.print("   - Breakout (30%)")

    # Simulacija kombinovanih signala
    console.print("\n📊 Simulacija kombinovanih signala...")

    # Dodaj test podatke u sve strategije
    test_data = []
    base_price = 48000.0

    for i in range(40):
        price_change = np.random.normal(0.002, 0.01)
        base_price *= (1 + price_change)
        volume = np.random.uniform(1000, 1500)

        market_data = MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            open=base_price * 0.999,
            high=base_price * 1.002,
            low=base_price * 0.998,
            close=base_price,
            volume=volume
        )

        # Dodaj u sve strategije
        for strategy in strategies:
            strategy.add_data("BTC/USDT", market_data)

        test_data.append(market_data)

    # Analiziraj sve strategije
    all_signals = await multi_manager.analyze_all("BTC/USDT", test_data[-10:])

    if all_signals:
        console.print(f"🎯 Generisano {len(all_signals)} signala:")

        for signal in all_signals:
            console.print(f"   - {signal.strategy}: {signal.action.upper()} (snaga: {signal.strength:.3f})")

        # Kombinovani signal
        combined = multi_manager.combine_signals(all_signals)
        if combined:
            console.print(f"\n🎯 Finalni kombinovani signal:")
            console.print(f"   Akcija: {combined.action.upper()}")
            console.print(f"   Snaga: {combined.strength:.3f}")
            console.print(f"   Cena: ${combined.price:.2f}")
        else:
            console.print("\n⚪ Nema kombinovanog signala")
    else:
        console.print("⚪ Nema signala od nijedne strategije")

async def main():
    """Glavna funkcija"""

    console.print("[bold red]🎯 CUSTOM STRATEGY EXAMPLES[/bold red]\n")

    await test_custom_strategies()
    await combine_custom_strategies()

    console.print("\n[bold green]🎉 Custom Strategy primeri završeni![/bold green]")
    console.print("\n[yellow]Ključne tačke:[/yellow]")
    console.print("1. Nasleđuj BaseStrategy klasu")
    console.print("2. Implementiraj analyze() metodu")
    console.print("3. Koristi get_dataframe() za pristup podacima")
    console.print("4. Vrati Signal objekat ili None")
    console.print("5. Kombinuj sa postojećim strategijama")

if __name__ == "__main__":
    asyncio.run(main())