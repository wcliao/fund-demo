import pandas as pd

from database import repository as repo
from database.init_db import build_database
from services.analysis_service import run_strategy_backtest, save_backtests


def test_config_versioning(tmp_path):
    conn = repo.connect(tmp_path / "t.db")
    repo.init_schema(conn)
    a = repo.get_or_create_config(conn, "momentum", {"weights": {"3M": 0.2}})
    b = repo.get_or_create_config(conn, "momentum", {"weights": {"3M": 0.2}})
    c = repo.get_or_create_config(conn, "momentum", {"weights": {"3M": 0.3}})
    assert a == b and c != a
    assert len(repo.list_configs(conn)) == 2
    conn.close()


def test_build_and_roundtrip(tmp_path, demo_data):
    db = tmp_path / "demo.db"
    build_database(db)
    conn = repo.connect(db)
    master = repo.load_master(conn)
    nav = repo.load_nav_wide(conn)
    _, expected = demo_data
    pd.testing.assert_frame_equal(nav, expected, check_freq=False, check_names=False)
    assert len(master) == 10

    res = run_strategy_backtest(nav, master["expense_ratio"], "momentum")
    ids = save_backtests(conn, {"momentum": res})
    counts = repo.table_counts(conn)
    assert counts["backtest_run"] == 1 and counts["backtest_daily"] == len(res[0].daily)
    assert counts["backtest_trades"] == len(res[0].trades)
    assert ids["momentum"] == 1
    conn.close()

    build_database(db)  # 重建會清空衍生結果
    conn = repo.connect(db)
    assert repo.table_counts(conn)["backtest_run"] == 0
    conn.close()
