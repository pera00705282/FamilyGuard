from datetime import datetime, timezone

import pytest

from crypto_trading.portfolio.manager import (
    Balance,
    PortfolioManager,
    PositionType,
    RiskManager,
)


def current_time() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def portfolio() -> PortfolioManager:
    return PortfolioManager(initial_balance=10000.0, base_currency="USDT")


def test_open_and_close_position_updates_balances(portfolio: PortfolioManager):
    # Open position
    assert portfolio.open_position(
        symbol="BTC/USDT",
        side="buy",
        size=0.1,
        entry_price=20000,
        exchange="binance",
    )

    assert "BTC/USDT" in portfolio.positions
    base_balance = portfolio.balances["USDT"]
    assert pytest.approx(base_balance.free) == 10000 - 0.1 * 20000

    # Update price and close position
    realized = portfolio.close_position("BTC/USDT", exit_price=21000)
    assert realized == pytest.approx(0.1 * (21000 - 20000))
    assert "BTC/USDT" not in portfolio.positions
    assert base_balance.used == 0
    assert pytest.approx(base_balance.total, rel=1e-5) == 10000 + realized


def test_calculate_position_size_respects_risk(portfolio: PortfolioManager):
    size = portfolio.calculate_position_size(
        symbol="BTC/USDT",
        price=20000,
        risk_amount=100,
        stop_loss_pct=0.02,
    )
    # Risk 100 at 2% stop means position value <= 5000, so size <= 0.25
    assert size <= 0.25


def test_get_portfolio_summary_includes_positions(portfolio: PortfolioManager):
    portfolio.open_position("ETH/USDT", "buy", 1, 2000, "binance")
    portfolio.update_position_prices({"ETH/USDT": 2100})

    summary = portfolio.get_portfolio_summary()
    assert summary["open_positions"] == 1
    assert summary["positions"][0]["symbol"] == "ETH/USDT"
    assert summary["positions"][0]["unrealized_pnl"] > 0


def test_save_and_load_state(tmp_path, portfolio: PortfolioManager):
    portfolio.open_position("BTC/USDT", "buy", 0.1, 20000, "binance")
    file_path = tmp_path / "portfolio.json"
    portfolio.save_state(str(file_path))

    new_portfolio = PortfolioManager()
    new_portfolio.load_state(str(file_path))

    assert "BTC/USDT" in new_portfolio.positions
    assert new_portfolio.positions["BTC/USDT"].entry_price == 20000


def test_risk_manager_validate_trade_limits_drawdown(portfolio: PortfolioManager):
    risk = RiskManager(max_drawdown=0.01)
    # Force drawdown by manipulating peak and total balance
    portfolio.peak_balance = 10000
    portfolio.balances["USDT"] = Balance("USDT", free=9000, used=0, total=9000)

    approved, reason = risk.validate_trade(
        portfolio=portfolio,
        symbol="BTC/USDT",
        side="buy",
        size=0.1,
        price=20000,
        stop_loss=18000,
    )
    assert not approved
    assert "drawdown" in reason.lower()


def test_risk_manager_position_concentration_check(portfolio: PortfolioManager):
    risk = RiskManager(max_risk_per_trade=0.05)
    portfolio.open_position("BTC/USDT", "buy", 0.1, 20000, "binance")

    approved, reason = risk.validate_trade(
        portfolio=portfolio,
        symbol="ETH/USDT",
        side="buy",
        size=0.5,
        price=10000,
        stop_loss=9000,
    )
    assert not approved
    assert "concentration" in reason.lower()

