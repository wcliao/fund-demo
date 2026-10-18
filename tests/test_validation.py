import pandas as pd
import pytest

from services.analysis_service import run_all_backtests
from services.validation_service import (MOMENTUM_PRESETS, SPLIT_DATE, momentum_preset_test, seed_robustness,
                                         seed_summary, segment_metrics, split_table)


def test_segment_metrics_rebases_and_filters_trades():
    idx = pd.bdate_range("2023-12-27", periods=6)
    eq = pd.Series([100, 110, 121, 121, 133.1, 133.1], index=idx, dtype=float)
    trades = pd.DataFrame({"exec_date": [idx[1], idx[4]], "amount": [50.0, 60.0], "cost": [0.1, 0.12]})
    a = segment_metrics(eq, trades, end=SPLIT_DATE)
    b = segment_metrics(eq, trades, start=SPLIT_DATE)
    assert a["cumulative_return"] == pytest.approx(0.21)
    assert a["total_cost"] == pytest.approx(0.1)
    assert b["cumulative_return"] == pytest.approx(133.1 / 121 - 1)
    assert b["total_cost"] == pytest.approx(0.12)


def test_split_table_ranks(demo_data):
    master, nav = demo_data
    sp = split_table(run_all_backtests(nav, master["expense_ratio"]))
    assert sorted(sp["in_rank"]) == [1, 2, 3, 4] and sorted(sp["out_rank"]) == [1, 2, 3, 4]


def test_preset_test_covers_all_presets(demo_data):
    master, nav = demo_data
    pt = momentum_preset_test(nav, master["expense_ratio"])
    assert set(pt.index) == set(MOMENTUM_PRESETS)
    assert list(pt["in_rank"]) == sorted(pt["in_rank"])


def test_seed_robustness_summary():
    df = seed_robustness([1, 2])
    assert len(df) == 2 * 4
    summ = seed_summary(df)
    assert summ["top_ratio"].sum() == pytest.approx(1.0)
    assert summ.loc["benchmark", "beat_ratio"] == 0
