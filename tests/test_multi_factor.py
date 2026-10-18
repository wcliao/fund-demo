import math

import numpy as np
import pandas as pd
import pytest

import config
from strategies.common import annualized_volatility, max_drawdown, percentile_score, sharpe_ratio
from strategies.multi_factor import compute_factors, score_factors


def test_volatility_manual():
    r = pd.Series([0.01, -0.01, 0.02, 0.0])
    assert annualized_volatility(r) == pytest.approx(np.std(r, ddof=1) * math.sqrt(252))


def test_sharpe_manual():
    r = pd.Series([0.01, -0.01, 0.02, 0.0])
    expected = (r.mean() * 252 - 0.01) / (r.std(ddof=1) * math.sqrt(252))
    assert sharpe_ratio(r, 0.01) == pytest.approx(expected)


def test_max_drawdown_positive():
    nav = pd.Series([100, 120, 90, 110, 80, 130])
    assert max_drawdown(nav) == pytest.approx(1 - 80 / 120)
    assert max_drawdown(nav) > 0


def test_percentile_basic_and_reverse():
    s = pd.Series({"A": 1.0, "B": 2.0, "C": 3.0})
    assert percentile_score(s).to_dict() == {"A": 0.0, "B": 50.0, "C": 100.0}
    assert percentile_score(s, higher_is_better=False).to_dict() == {"A": 100.0, "B": 50.0, "C": 0.0}


def test_percentile_ties_average_rank():
    s = pd.Series({"A": 1.0, "B": 1.0, "C": 3.0, "D": 4.0})
    out = percentile_score(s)
    # rank_avg：A,B=1.5 → (0.5/3)*100
    assert out["A"] == pytest.approx(50 / 3) and out["A"] == out["B"]
    assert out["D"] == 100


def test_percentile_all_equal_and_small_sample():
    assert (percentile_score(pd.Series({"A": 1.0, "B": 1.0, "C": 1.0})) == 50).all()
    assert percentile_score(pd.Series({"A": 1.0, "B": 2.0, "C": np.nan})).isna().all()


def test_score_weights_and_contribution(demo_data):
    master, nav = demo_data
    raw = compute_factors(nav, master["expense_ratio"])
    scored, eff = score_factors(raw)
    assert sum(eff.values()) == pytest.approx(1)
    row = scored.loc["F001"]
    total = sum(row[f"s_{k}"] * config.DEFAULT_FACTOR_WEIGHTS[k] for k in config.FACTORS)
    assert row["score"] == pytest.approx(total)
    assert row["score"] == pytest.approx(sum(row[f"c_{k}"] for k in config.FACTORS))


def test_f010_scores_below_f002_on_expense(demo_data):
    master, nav = demo_data
    raw = compute_factors(nav, master["expense_ratio"])
    scored, _ = score_factors(raw)
    assert scored.loc["F010", "s_expense"] < scored.loc["F002", "s_expense"]
    assert scored.loc["F010", "score"] < scored.loc["F002", "score"]


def test_factor_window_uses_252_days(demo_data):
    master, nav = demo_data
    raw = compute_factors(nav, master["expense_ratio"])
    win = nav["F001"].iloc[-253:]
    assert raw.loc["F001", "drawdown"] == pytest.approx(max_drawdown(win))


def test_insufficient_factor_sample_reweights():
    raw = pd.DataFrame({"momentum": [0.1, 0.2, 0.3], "volatility": [0.1, 0.2, 0.3],
                        "sharpe": [1.0, 0.5, np.nan], "drawdown": [0.1, 0.2, 0.3],
                        "expense": [0.01, 0.02, 0.03]}, index=["A", "B", "C"])
    raw.loc[["A", "B"], "sharpe"] = [1.0, np.nan]  # 只剩 1 筆有效 → 不評分
    _, eff = score_factors(raw)
    assert eff["sharpe"] == 0
    assert sum(eff.values()) == pytest.approx(1)
