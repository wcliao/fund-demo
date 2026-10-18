import copy

import numpy as np
import pandas as pd

import config
from simulation.generate_funds import data_fingerprint, generate_funds, trading_calendar
from simulation.validate import check_data, check_scenarios


def test_calendar_and_shape(demo_data):
    master, nav = demo_data
    assert nav.shape == (1260, 10)
    assert nav.index[0] == pd.Timestamp("2021-01-04")
    assert (nav.index.dayofweek < 5).all()
    assert (nav.iloc[0] == 100).all()
    assert list(master.index) == config.FUND_IDS


def test_reproducible():
    _, a = generate_funds()
    _, b = generate_funds()
    pd.testing.assert_frame_equal(a, b)
    assert data_fingerprint(a) == data_fingerprint(b)


def test_change_one_fund_does_not_affect_others():
    funds = copy.deepcopy(config.FUNDS)
    funds[4]["phases"] = [(0, 1259, 0.5, 0.5)]  # 修改 F005
    _, base = generate_funds()
    _, changed = generate_funds(funds)
    pd.testing.assert_series_equal(base["F001"], changed["F001"])
    assert not np.allclose(base["F005"], changed["F005"])


def test_different_seed_changes_data():
    _, a = generate_funds(seed=42)
    _, b = generate_funds(seed=7)
    assert not np.allclose(a.to_numpy(), b.to_numpy())


def test_f010_always_below_f002(demo_data):
    _, nav = demo_data
    assert (nav["F010"].iloc[1:] < nav["F002"].iloc[1:]).all()


def test_data_checks_pass(demo_data):
    master, nav = demo_data
    assert all(c.passed for c in check_data(master, nav))


def test_data_check_detects_bad_nav(demo_data):
    master, nav = demo_data
    bad = nav.copy()
    bad.iloc[5, 0] = -1
    assert not all(c.passed for c in check_data(master, bad))


def test_scenarios_pass(demo_data):
    _, nav = demo_data
    failed = [c for c in check_scenarios(nav) if not c.passed]
    assert not failed, failed


def test_calendar_length():
    assert len(trading_calendar()) == config.N_DAYS
