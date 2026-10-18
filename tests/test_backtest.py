import numpy as np
import pandas as pd
import pytest

import config
from backtest.engine import rebalance, run_backtest, signal_indices
from backtest.metrics import compute_metrics
from services.analysis_service import run_strategy_backtest
from strategies import momentum


def test_first_signal_date(demo_data):
    _, nav = demo_data
    idx = signal_indices(nav.index)
    assert nav.index[idx[0]] == pd.Timestamp("2021-12-31")
    assert all(i >= 252 for i in idx)


def test_signal_uses_only_past_data(demo_data):
    """修改 t+1 之後的 NAV 不影響 t 日訊號。"""
    _, nav = demo_data
    t = signal_indices(nav.index)[0]
    before = momentum.select_top(nav.iloc[: t + 1])
    tampered = nav.copy()
    tampered.iloc[t + 1:] = tampered.iloc[t + 1:] * np.linspace(0.1, 5, len(tampered) - t - 1)[:, None]
    after = momentum.select_top(tampered.iloc[: t + 1])
    assert before == after


def test_selector_receives_history_up_to_signal_day(demo_data):
    _, nav = demo_data
    seen = []

    def spy(hist):
        seen.append(hist.index[-1])
        return {"F001": 1.0}

    res = run_backtest(nav, spy)
    assert seen == list(res.signals["signal_date"])
    assert all(s in nav.index for s in seen)


def test_execution_at_next_day_nav(demo_data):
    _, nav = demo_data
    res = run_backtest(nav, lambda h: {"F001": 1.0})
    first = res.trades.iloc[0]
    t = nav.index.get_loc(first["signal_date"])
    assert first["exec_date"] == nav.index[t + 1]
    assert first["price"] == pytest.approx(nav["F001"].iloc[t + 1])


def test_cost_charged_on_initial_buy_and_both_sides():
    prices = pd.Series({"A": 10.0, "B": 20.0})
    units, cash, trades = rebalance({}, 1_000_000, prices, {"A": 1.0}, 0.002)
    assert trades[0]["side"] == "買進"
    assert trades[0]["cost"] == pytest.approx(0.002 * trades[0]["amount"])
    assert cash >= 0
    assert units["A"] * 10 + cash + trades[0]["cost"] == pytest.approx(1_000_000)
    # 全換倉：賣 A 買 B，兩邊都收成本
    units2, cash2, trades2 = rebalance(units, cash, prices, {"B": 1.0}, 0.002)
    sides = {t["side"] for t in trades2}
    assert sides == {"買進", "賣出"}
    total_cost = sum(t["cost"] for t in trades2)
    assert total_cost == pytest.approx(0.002 * sum(t["amount"] for t in trades2))
    assert cash2 >= 0
    value_before = units["A"] * 10 + cash
    assert units2["B"] * 20 + cash2 + total_cost == pytest.approx(value_before)


def test_all_cash_target_sells_everything():
    prices = pd.Series({"A": 10.0})
    units, cash, trades = rebalance({"A": 100.0}, 0.0, prices, {}, 0.002)
    assert units == {} and cash == pytest.approx(1000 * 0.998)


def test_benchmark_also_pays_cost(demo_data):
    master, nav = demo_data
    res, metrics = run_strategy_backtest(nav, master["expense_ratio"], "benchmark")
    assert metrics["total_cost"] > 0
    assert (res.daily["cash"] >= 0).all()


def test_no_trade_on_last_day_signal(demo_data):
    _, nav = demo_data
    res = run_backtest(nav, lambda h: {"F001": 1.0})
    assert nav.index[-1] not in set(res.signals["signal_date"])


def test_metrics_manual():
    eq = pd.Series([1_000_000, 1_100_000, 990_000.0])
    trades = pd.DataFrame({"amount": [1_000_000.0], "cost": [2000.0]})
    m = compute_metrics(eq, trades)
    assert m["cumulative_return"] == pytest.approx(-0.01)
    assert m["max_drawdown"] == pytest.approx(0.1)
    assert m["total_cost"] == 2000
    assert m["annual_return"] == pytest.approx(0.99 ** (252 / 2) - 1)


def test_cost_rate_constant():
    assert config.COST_RATE == 0.002
