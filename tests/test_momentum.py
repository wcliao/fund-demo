import math

import numpy as np
import pandas as pd
import pytest

from strategies.common import normalize_weights, period_return, rank_desc
from strategies.momentum import compute_momentum


def test_period_return_manual():
    nav = pd.Series([100, 110, 121])
    assert period_return(nav, 1) == pytest.approx(0.10)
    assert period_return(nav, 2) == pytest.approx(0.21)


def test_period_return_insufficient():
    assert math.isnan(period_return(pd.Series([100, 101]), 2))


def test_momentum_score_formula():
    n = 253
    nav = pd.DataFrame({"A": np.linspace(100, 200, n), "B": np.linspace(100, 150, n)},
                       index=pd.bdate_range("2021-01-04", periods=n))
    df = compute_momentum(nav)
    a = nav["A"]
    expected = (0.2 * (a.iloc[-1] / a.iloc[-64] - 1) + 0.3 * (a.iloc[-1] / a.iloc[-127] - 1)
                + 0.5 * (a.iloc[-1] / a.iloc[0] - 1))
    assert df.loc["A", "score"] == pytest.approx(expected)
    assert df.loc["A", "rank"] == 1 and df.loc["B", "rank"] == 2


def test_momentum_insufficient_data():
    nav = pd.DataFrame({"A": np.linspace(100, 120, 252)}, index=pd.bdate_range("2021-01-04", periods=252))
    df = compute_momentum(nav)
    assert math.isnan(df.loc["A", "score"]) and df.loc["A", "status"] == "資料不足"


def test_normalize_weights():
    assert normalize_weights({"a": 20, "b": 30, "c": 50}) == pytest.approx({"a": 0.2, "b": 0.3, "c": 0.5})


@pytest.mark.parametrize("w", [{"a": 0, "b": 0}, {"a": -1, "b": 2}])
def test_normalize_weights_invalid(w):
    with pytest.raises(ValueError):
        normalize_weights(w)


def test_rank_tie_break_by_fund_id():
    r = rank_desc(pd.Series({"F003": 1.0, "F001": 1.0, "F002": 2.0, "F004": np.nan}))
    assert r["F002"] == 1 and r["F001"] == 2 and r["F003"] == 3 and math.isnan(r["F004"])
