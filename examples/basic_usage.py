#!/usr/bin/env python3
"""



Basic Usage Example
==================

Osnovni primer korišćenja crypto trading automation tool-a.
"""


# Dodaj src direktorijum u Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


console = Console()

async def basic_example():
    """Osnovni primer korišćenja"""

    console.print("[bold blue]🚀 Basic Usage Example[/bold blue]")

    # Setup logging
    setup_logging(level="INFO")

    try:
        # 1. Kreiranje trading bot-a
        console.print("1. Kreiranje trading bot-a...")
        bot = TradingBot("config/config.yaml")

        # 2. Inicijalizacija
        console.print("2. Inicijalizacija...")
        await bot.initialize()

        # 3. Kreiranje strategija
        console.print("3. Kreiranje strategija...")
        ma_strategy = MovingAverageCrossStrategy(fast_period=10, slow_period=30)
        rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)

        # 4. Multi-strategy manager
        strategies = [ma_strategy, rsi_strategy]
        weights = {'MA_Cross': 0.6, 'RSI': 0.4}
        strategy_manager = MultiStrategyManager(strategies, weights)

        # 5. Dodavanje strategija u bot
        bot.strategy_manager = strategy_manager

        # 6. Pokretanje u dry-run modu
        console.print("4. Pokretanje u dry-run modu...")
        bot.dry_run = True

        # Pokreni za kratko vreme (30 sekundi)
        console.print("5. Bot radi 30 sekundi...")

        # Simulacija rada
        import time
        start_time = time.time()

        while time.time() - start_time < 30:
            # Ovde bi bio glavni trading loop
            await asyncio.sleep(1)

            # Prikaži status svakih 10 sekundi
            if int(time.time() - start_time) % 10 == 0:
                console.print(f"⏱️ Vreme rada: {int(time.time() - start_time)}s")

        console.print("[green]✅ Primer završen uspešno![/green]")

    except Exception as e:
        console.print(f"[red]❌ Greška: {e}[/red]")

    finally:
        # Cleanup
        if 'bot' in locals():
            await bot.shutdown()

async def portfolio_example():
    """Primer portfolio management-a"""

    console.print("\n[bold green]💰 Portfolio Management Example[/bold green]")

    # Kreiranje portfolio managera
    portfolio = PortfolioManager(initial_balance=10000.0, base_currency="USDT")

    console.print(f"Početni balance: ${portfolio.initial_balance}")

    # Simulacija nekoliko trade-ova
    trades = [
        ("BTC/USDT", "buy", 0.1, 50000.0),
        ("ETH/USDT", "buy", 2.0, 3000.0),
        ("ADA/USDT", "buy", 1000.0, 1.0),
    ]

    for symbol, side, size, price in trades:
        success = portfolio.open_position(symbol, side, size, price, "example")
        if success:
            console.print(f"✅ Otvorena pozicija: {symbol} {side} {size} @ ${price}")
        else:
            console.print(f"❌ Neuspešno otvaranje: {symbol}")

    # Simulacija price update-a
    price_updates = {
        "BTC/USDT": 51000.0,  # +2%
        "ETH/USDT": 3150.0,   # +5%
        "ADA/USDT": 1.05,     # +5%
    }

    portfolio.update_position_prices(price_updates)

    # Portfolio summary
    summary = portfolio.get_portfolio_summary(price_updates)

    console.print(f"\n📊 Portfolio Summary:")
    console.print(f"Total Balance: ${summary['total_balance']:.2f}")
    console.print(f"Total PnL: ${summary['total_pnl']:.2f}")
    console.print(f"Return: {summary['total_return_pct']:.2f}%")
    console.print(f"Open Positions: {summary['open_positions']}")

async def strategy_example():
    """Primer trading strategija"""

    console.print("\n[bold yellow]📈 Strategy Example[/bold yellow]")

    # Kreiranje strategije
    ma_strategy = MovingAverageCrossStrategy(fast_period=5, slow_period=15)

    # Simulacija market podataka
    from crypto_trading.strategies import MarketData
    from datetime import datetime

    sample_data = []
    base_price = 50000.0

    for i in range(30):
        # Trend pattern
        price_change = 0.01 if i < 15 else -0.01
        base_price *= (1 + price_change)

        market_data = MarketData(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            open=base_price * 0.999,
            high=base_price * 1.002,
            low=base_price * 0.998,
            close=base_price,
            volume=1000.0
        )

        ma_strategy.add_data("BTC/USDT", market_data)
        sample_data.append(market_data)

    # Analiza strategije
    signal = await ma_strategy.analyze("BTC/USDT", sample_data[-10:])

    if signal:
        console.print(f"🎯 Signal: {signal.action.upper()} {signal.symbol}")
        console.print(f"   Strategija: {signal.strategy}")
        console.print(f"   Snaga: {signal.strength:.2f}")
        console.print(f"   Cena: ${signal.price:.2f}")
    else:
        console.print("⚪ Nema signala u ovom trenutku")

async def main():
    """Glavna funkcija"""

    console.print("[bold red]🎯 CRYPTO TRADING AUTOMATION - BASIC EXAMPLES[/bold red]\n")

    # Pokreni sve primere
    await basic_example()
    await portfolio_example()
    await strategy_example()

    console.print("\n[bold green]🎉 Svi primeri završeni![/bold green]")
    console.print("\n[yellow]Sledeći koraci:[/yellow]")
    console.print("1. Konfiguriši config/config.yaml sa svojim API ključevima")
    console.print("2. Pokreni: python scripts/crypto_trading_cli.py validate")
    console.print("3. Testiraj: python scripts/crypto_trading_cli.py test")
    console.print("4. Pokreni: python scripts/crypto_trading_cli.py run --dry-run")

if __name__ == "__main__":
    asyncio.run(main())