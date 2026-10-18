"""SQLite 資料存取層。"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
TABLES = ["backtest_trades", "backtest_daily", "backtest_run", "strategy_result", "strategy_config",
          "fund_nav", "fund_master"]


def connect(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def reset_all(conn: sqlite3.Connection) -> None:
    """清空所有資料表（含衍生結果）。"""
    for t in TABLES:
        conn.execute(f"DELETE FROM {t}")
    if _has_sequence(conn):
        conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()


def _has_sequence(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone() is not None


def save_funds(conn: sqlite3.Connection, master: pd.DataFrame, nav_wide: pd.DataFrame) -> None:
    m = master.reset_index()
    conn.executemany(
        "INSERT INTO fund_master (fund_id, name, category, currency, expense_ratio, scenario_type, purpose,"
        " data_source) VALUES (?,?,?,?,?,?,?,?)",
        m[["fund_id", "name", "category", "currency", "expense_ratio", "scenario_type", "purpose",
           "data_source"]].itertuples(index=False, name=None),
    )
    long = nav_wide.reset_index().melt(id_vars="nav_date", var_name="fund_id", value_name="nav")
    long["nav_date"] = long["nav_date"].dt.strftime("%Y-%m-%d")
    conn.executemany("INSERT INTO fund_nav (fund_id, nav_date, nav) VALUES (?,?,?)",
                     long[["fund_id", "nav_date", "nav"]].itertuples(index=False, name=None))
    conn.commit()


def fund_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM fund_master").fetchone()[0]


def load_master(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM fund_master ORDER BY fund_id", conn).set_index("fund_id")


def load_nav_wide(conn: sqlite3.Connection) -> pd.DataFrame:
    long = pd.read_sql("SELECT fund_id, nav_date, nav FROM fund_nav", conn, parse_dates=["nav_date"])
    wide = long.pivot(index="nav_date", columns="fund_id", values="nav").sort_index()
    wide.columns.name = None
    return wide


def params_hash(strategy_id: str, params: dict) -> str:
    payload = json.dumps({"strategy_id": strategy_id, "params": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def get_or_create_config(conn: sqlite3.Connection, strategy_id: str, params: dict) -> int:
    """相同參數重用 config_id；不同參數新增一列，不覆寫舊版本。"""
    h = params_hash(strategy_id, params)
    row = conn.execute("SELECT config_id FROM strategy_config WHERE params_hash=?", (h,)).fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO strategy_config (strategy_id, params_json, params_hash, created_at) VALUES (?,?,?,?)",
        (strategy_id, json.dumps(params, sort_keys=True, ensure_ascii=False), h,
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_configs(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("SELECT config_id, strategy_id, params_json, created_at FROM strategy_config"
                       " ORDER BY config_id DESC", conn)


def save_strategy_results(conn: sqlite3.Connection, config_id: int, strategy_id: str, eval_date: str,
                          results: pd.DataFrame) -> int:
    """results：index 為 fund_id，需含 score、rank；其餘欄位存入 details_json。"""
    rows = []
    for fid, r in results.iterrows():
        details = {k: (None if pd.isna(v) else (v if isinstance(v, (str, int)) else float(v)))
                   for k, v in r.items() if k not in ("score", "rank") and not isinstance(v, (dict, list))}
        rows.append((config_id, fid, eval_date, strategy_id,
                     None if pd.isna(r.get("score")) else float(r["score"]),
                     None if pd.isna(r.get("rank")) else int(r["rank"]),
                     json.dumps(details, ensure_ascii=False, default=str)))
    conn.executemany(
        "INSERT OR REPLACE INTO strategy_result (config_id, fund_id, eval_date, strategy_id, score, rank,"
        " details_json) VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def load_strategy_results(conn: sqlite3.Connection, config_id: int) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM strategy_result WHERE config_id=? ORDER BY eval_date, rank",
                       conn, params=(config_id,))


def save_backtest(conn: sqlite3.Connection, strategy_id: str, config_id: int, cost_rate: float,
                  daily: pd.DataFrame, trades: pd.DataFrame, metrics: dict) -> int:
    cur = conn.execute(
        "INSERT INTO backtest_run (strategy_id, config_id, cost_rate, start_date, end_date, metrics_json,"
        " created_at) VALUES (?,?,?,?,?,?,?)",
        (strategy_id, config_id, cost_rate, daily.index[0].strftime("%Y-%m-%d"),
         daily.index[-1].strftime("%Y-%m-%d"), json.dumps(metrics), datetime.now().isoformat(timespec="seconds")),
    )
    run_id = int(cur.lastrowid)
    conn.executemany(
        "INSERT INTO backtest_daily (run_id, nav_date, equity, cash, positions_json) VALUES (?,?,?,?,?)",
        [(run_id, d.strftime("%Y-%m-%d"), float(r.equity), float(r.cash),
          json.dumps({k: float(v) for k, v in r.positions.items()})) for d, r in daily.iterrows()],
    )
    conn.executemany(
        "INSERT INTO backtest_trades (run_id, signal_date, exec_date, fund_id, side, amount, units, cost)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [(run_id, t.signal_date.strftime("%Y-%m-%d"), t.exec_date.strftime("%Y-%m-%d"), t.fund_id, t.side,
          float(t.amount), float(t.units), float(t.cost)) for t in trades.itertuples()],
    )
    conn.commit()
    return run_id


def list_backtest_runs(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT r.run_id, r.strategy_id, r.config_id, c.params_json, r.cost_rate, r.start_date, r.end_date,"
        " r.metrics_json, r.created_at FROM backtest_run r JOIN strategy_config c USING (config_id)"
        " ORDER BY r.run_id DESC", conn)


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in reversed(TABLES)}
