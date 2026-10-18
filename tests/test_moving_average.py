import numpy as np
import pandas as pd
import pytest

from strategies.moving_average import (BEAR, BULL, DEATH, GOLDEN, MIXED, classify_state, detect_crosses,
                                       sma)


def test_sma_values_and_nan():
    s = pd.Series([1.0, 2, 3, 4, 5])
    out = sma(s, 3)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == pytest.approx(2.0) and out.iloc[4] == pytest.approx(4.0)


def test_classify_state():
    assert classify_state(110, 105, 100) == BULL
    assert classify_state(90, 95, 100) == BEAR
    assert classify_state(110, 95, 100) == MIXED
    assert classify_state(np.nan, 95, 100) == "資料不足"


def test_cross_only_on_crossing_day():
    short = pd.Series([1.0, 2, 3, 4, 3, 2])
    long = pd.Series([2.5, 2.5, 2.5, 2.5, 2.5, 2.5])
    ev = detect_crosses(short, long)
    assert ev.iloc[2] == GOLDEN
    assert ev.iloc[5] == DEATH
    assert ev.notna().sum() == 2


def test_equal_is_not_crossing():
    short = pd.Series([1.0, 2.0, 2.0, 3.0])
    long = pd.Series([2.0, 2.0, 2.0, 2.0])
    ev = detect_crosses(short, long)
    # 1→2：從下方變相等，不是穿越；2→3：前一日相等（≤）今日高於，成立黃金交叉
    assert pd.isna(ev.iloc[1]) and pd.isna(ev.iloc[2])
    assert ev.iloc[3] == GOLDEN


def test_no_event_on_first_valid_day():
    short = pd.Series([np.nan, 3.0, 4.0])
    long = pd.Series([np.nan, 2.0, 2.0])
    assert detect_crosses(short, long).notna().sum() == 0
