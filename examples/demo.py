#!/usr/bin/env python3
"""



Demo Script za Crypto Trading Automation Tool
==============================================

Ovaj script demonstrira osnovne funkcionalnosti alata.
"""


# Lokalni imports
    MovingAverageCrossStrategy,
    RSIStrategy,
    MACDStrategy,
    MultiStrategyManager,
    MarketData,
    create_conservative_strategy,
    create_aggressive_strategy
)

console = Console()

async def demo_strategies():
    """Demo trading strategija"""
    console.print(Panel.fit(
        "[bold blue]📊 DEMO: Trading Strategije[/bold blue]",
        title="Strategije"
    ))

    # Kreiranje strategija
    ma_strategy = MovingAverageCrossStrategy(fast_period=10, slow_period=30)
    rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)
    macd_strategy = MACDStrategy()

    # Multi-strategy manager
    strategies = [ma_strategy, rsi_strategy, macd_strategy]
    weights = {'MA_Cross': 0.4, 'RSI': 0.3, 'MACD': 0.3}
    multi_strategy = MultiStrategyManager(strategies, weights)

    console.print("✅ Kreiran Multi-Strategy Manager sa 3 strategije")

    # Simulacija market podataka
    sample_data = []
    base_price = 50000.0

    for i in range(50):
        # Simulacija price movement
        price_change = 0.01 if i % 10 < 5 else -0.01  # Trend pattern
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
        sample_data.append(market_data)

    console.print(f"📈 Generisano {len(sample_data)} market data points")

    # Analiza strategija
    signals = await multi_strategy.analyze_all("BTC/USDT", sample_data)

    if signals:
        table = Table(title="Trading Signali")
        table.add_column("Strategija", style="cyan")
        table.add_column("Akcija", style="yellow")
        table.add_column("Snaga", style="green")
        table.add_column("Cena", style="blue")

        for signal in signals:
            color = "green" if signal.action == "buy" else "red"
            table.add_row(
                signal.strategy,
                f"[{color}]{signal.action.upper()}[/{color}]",
                f"{signal.strength:.2f}",
                f"${signal.price:.2f}"
            )

        console.print(table)

        # Kombinovani signal
        combined_signal = multi_strategy.combine_signals(signals)
        if combined_signal:
            console.print(f"🎯 Finalni signal: [{combined_signal.action.upper()}] "
                         f"sa snagom {combined_signal.strength:.2f}")
    else:
        console.print("⚪ Nema trading signala u ovom trenutku")

async def demo_portfolio_management():
    """Demo portfolio management-a"""
    console.print(Panel.fit(
        "[bold green]💰 DEMO: Portfolio Management[/bold green]",
        title="Portfolio"
    ))

    # Kreiranje portfolio managera
    portfolio = PortfolioManager(initial_balance=10000.0, base_currency="USDT")
    risk_manager = RiskManager(
        max_risk_per_trade=0.02,
        max_portfolio_risk=0.1,
        max_drawdown=0.15
    )

    console.print("✅ Kreiran Portfolio Manager sa $10,000 početnim balansom")

    # Simulacija trgovanja
    trades = [
        ("BTC/USDT", "buy", 0.1, 50000.0, 49000.0, 52000.0),  # Profitable trade
        ("ETH/USDT", "buy", 2.0, 3000.0, 2900.0, 3200.0),     # Profitable trade
        ("ADA/USDT", "buy", 1000.0, 1.0, 0.95, 1.05),         # Small profitable trade
    ]

    for symbol, side, size, entry_price, stop_loss, take_profit in trades:
        # Validacija trade-a
        is_valid, message = risk_manager.validate_trade(
            portfolio, symbol, side, size, entry_price, stop_loss
        )

        if is_valid:
            success = portfolio.open_position(
                symbol, side, size, entry_price, "demo",
                stop_loss=stop_loss, take_profit=take_profit
            )
            if success:
                console.print(f"✅ Otvorena pozicija: {symbol} {side} {size} @ ${entry_price}")
            else:
                console.print(f"❌ Neuspešno otvaranje pozicije: {symbol}")
        else:
            console.print(f"⚠️ Trade odbačen: {message}")

    # Simulacija price updates
    price_updates = {
        "BTC/USDT": 51000.0,  # +2% profit
        "ETH/USDT": 3100.0,   # +3.33% profit
        "ADA/USDT": 1.02,     # +2% profit
    }

    portfolio.update_position_prices(price_updates)
    console.print("📊 Ažurirane cene pozicija")

    # Portfolio summary
    summary = portfolio.get_portfolio_summary(price_updates)

    summary_table = Table(title="Portfolio Pregled")
    summary_table.add_column("Metrika", style="cyan")
    summary_table.add_column("Vrednost", style="green")

    summary_table.add_row("Ukupan Balance", f"${summary['total_balance']:.2f}")
    summary_table.add_row("Početni Balance", f"${summary['initial_balance']:.2f}")
    summary_table.add_row("Ukupan PnL", f"${summary['total_pnl']:.2f}")
    summary_table.add_row("Nerealizovan PnL", f"${summary['unrealized_pnl']:.2f}")
    summary_table.add_row("Ukupan Return", f"{summary['total_return_pct']:.2f}%")
    summary_table.add_row("Trenutni Drawdown", f"{summary['current_drawdown']:.2f}%")
    summary_table.add_row("Otvorene Pozicije", str(summary['open_positions']))

    console.print(summary_table)

    # Pozicije tabela
    if summary['positions']:
        positions_table = Table(title="Otvorene Pozicije")
        positions_table.add_column("Symbol", style="cyan")
        positions_table.add_column("Side", style="yellow")
        positions_table.add_column("Size", style="blue")
        positions_table.add_column("Entry", style="white")
        positions_table.add_column("Current", style="white")
        positions_table.add_column("PnL", style="green")
        positions_table.add_column("PnL %", style="green")

        for pos in summary['positions']:
            pnl_color = "green" if pos['unrealized_pnl'] >= 0 else "red"
            positions_table.add_row(
                pos['symbol'],
                pos['side'],
                f"{pos['size']:.4f}",
                f"${pos['entry_price']:.2f}",
                f"${pos['current_price']:.2f}",
                f"[{pnl_color}]${pos['unrealized_pnl']:.2f}[/{pnl_color}]",
                f"[{pnl_color}]{pos['pnl_percentage']:.2f}%[/{pnl_color}]"
            )

        console.print(positions_table)

async def demo_monitoring():
    """Demo monitoring sistema"""
    console.print(Panel.fit(
        "[bold yellow]📊 DEMO: Monitoring Sistem[/bold yellow]",
        title="Monitoring"
    ))

    # Kreiranje monitoring komponenti
    metrics = MetricsCollector()
    alert_manager = AlertManager()

    console.print("✅ Kreiran Metrics Collector i Alert Manager")

    # Simulacija metrika
    import random

    for i in range(20):
        # Portfolio metrike
        metrics.record_metric('total_balance', 10000 + random.uniform(-500, 1000))
        metrics.record_metric('total_pnl', random.uniform(-200, 500))
        metrics.record_metric('drawdown_pct', random.uniform(0, 15))

        # API metrike
        metrics.record_metric('api_latency', random.uniform(50, 200))
        metrics.record_metric('api_error_rate', random.uniform(0, 0.05))

        # System metrike
        metrics.record_metric('cpu_usage_pct', random.uniform(10, 80))
        metrics.record_metric('memory_usage_pct', random.uniform(30, 70))

    console.print("📊 Generisano 20 metric points za svaku metriku")

    # Prikaz statistika
    metrics_table = Table(title="Metrike Statistike")
    metrics_table.add_column("Metrika", style="cyan")
    metrics_table.add_column("Min", style="green")
    metrics_table.add_column("Max", style="red")
    metrics_table.add_column("Avg", style="yellow")
    metrics_table.add_column("Current", style="blue")

    metric_names = ['total_balance', 'total_pnl', 'drawdown_pct', 'api_latency', 'cpu_usage_pct']

    for metric_name in metric_names:
        stats = metrics.get_metric_stats(metric_name, hours=24)
        if stats:
            metrics_table.add_row(
                metric_name,
                f"{stats['min']:.2f}",
                f"{stats['max']:.2f}",
                f"{stats['avg']:.2f}",
                f"{stats['current']:.2f}"
            )

    console.print(metrics_table)

    # Setup alert rules
    from crypto_trading.monitoring import Alert, AlertLevel

    alert_manager.add_alert_rule(
        'drawdown_pct', 'gt', 10.0,
        AlertLevel.WARNING,
        'Portfolio drawdown exceeded 10%: {value:.2f}%'
    )

    test_alert = Alert(
        level=AlertLevel.WARNING,
        title="Test Alert",
        message="Ovo je test alert za demo",
        timestamp=datetime.now(),
        source="Demo",
        metadata={'test': True}
    )

    await alert_manager.send_alert(test_alert)
    console.print("🔔 Poslat test alert")

async def demo_predefined_strategies():
    """Demo predefinisanih strategija"""
    console.print(Panel.fit(
        "[bold magenta]🎯 DEMO: Predefinisane Strategije[/bold magenta]",
        title="Strategije"
    ))

    # Kreiranje različitih strategija
    conservative = create_conservative_strategy()
    aggressive = create_aggressive_strategy()

    strategies_table = Table(title="Dostupne Strategije")
    strategies_table.add_column("Tip", style="cyan")
    strategies_table.add_column("Strategije", style="yellow")
    strategies_table.add_column("Opis", style="green")

    strategies_table.add_row(
        "Conservative",
        "MA(20,50) + RSI(14) + BB(20)",
        "Sigurna strategija sa dužim periodima"
    )

    strategies_table.add_row(
        "Aggressive",
        "MA(5,15) + RSI(7) + MACD + Volume",
        "Brža strategija sa kraćim periodima"
    )

    strategies_table.add_row(
        "Scalping",
        "MA(3,8) + RSI(5) + Volume",
        "Vrlo brza strategija za kratkoročno trgovanje"
    )

    console.print(strategies_table)

    console.print("✅ Sve strategije su dostupne i konfigurisane")

async def main():
    """Glavna demo funkcija"""
    console.print(Panel.fit(
        "[bold red]🚀 CRYPTO TRADING AUTOMATION TOOL - DEMO 🚀[/bold red]\n"
        "[yellow]Demonstracija funkcionalnosti alata[/yellow]",
        title="DEMO MODE"
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # Demo strategija
        task1 = progress.add_task("Demo Trading Strategije...", total=None)
        await demo_strategies()
        progress.update(task1, completed=True)

        await asyncio.sleep(2)

        # Demo portfolio management
        task2 = progress.add_task("Demo Portfolio Management...", total=None)
        await demo_portfolio_management()
        progress.update(task2, completed=True)

        await asyncio.sleep(2)

        # Demo monitoring
        task3 = progress.add_task("Demo Monitoring Sistem...", total=None)
        await demo_monitoring()
        progress.update(task3, completed=True)

        await asyncio.sleep(2)

        # Demo predefined strategies
        task4 = progress.add_task("Demo Predefinisane Strategije...", total=None)
        await demo_predefined_strategies()
        progress.update(task4, completed=True)

    console.print(Panel.fit(
        "[bold green]✅ DEMO ZAVRŠEN USPEŠNO! ✅[/bold green]\n\n"
        "[yellow]Sledeći koraci:[/yellow]\n"
        "1. Kreiraj konfiguraciju: [cyan]python crypto_trading_automation.py init[/cyan]\n"
        "2. Dodaj API ključeve u config.yaml\n"
        "3. Testiraj konekcije: [cyan]python crypto_trading_automation.py test[/cyan]\n"
        "4. Pokreni monitoring: [cyan]python crypto_trading_automation.py monitor[/cyan]\n"
        "5. Pokreni bot: [cyan]python crypto_trading_automation.py run[/cyan]\n\n"
        "[red]⚠️ PAŽNJA: Počni sa sandbox/demo modovima![/red]",
        title="ZAVRŠETAK"
    ))

if __name__ == "__main__":
    # Setup logging za demo
    logging.basicConfig(level=logging.WARNING)  # Smanji noise

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Demo prekinut od strane korisnika[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Greška u demo-u: {e}[/bold red]")