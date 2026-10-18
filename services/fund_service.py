"""基金資料服務：讀取主檔與 NAV、計算總覽報酬。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import config
from database import repository as repo
from database.init_db import ensure_database
from strategies.common import annualized_volatility, daily_returns, max_drawdown, period_return


def load_data(db_path: Path | str = config.DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_database(db_path)
    conn = repo.connect(db_path)
    try:
        return repo.load_master(conn), repo.load_nav_wide(conn)
    finally:
        conn.close()


def nav_until(nav_wide: pd.DataFrame, eval_date) -> pd.DataFrame:
    """只回傳評估日（含）以前的資料，避免使用未來資料。"""
    return nav_wide.loc[: pd.Timestamp(eval_date)]


def overview_table(master: pd.DataFrame, nav_hist: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for fid in nav_hist.columns:
        nav = nav_hist[fid]
        r = daily_returns(nav).iloc[1:]
        rows[fid] = {
            "最新 NAV": nav.iloc[-1],
            **{f"{k} 報酬": period_return(nav, n) for k, n in config.MOMENTUM_WINDOWS.items()},
            "成立以來報酬": nav.iloc[-1] / nav.iloc[0] - 1,
            "年化波動率（全期）": annualized_volatility(r),
            "最大回撤（全期）": max_drawdown(nav),
        }
    df = pd.DataFrame.from_dict(rows, orient="index")
    return master[["name", "category", "expense_ratio", "scenario_type"]].join(df)


def risk_level(vol: float) -> str:
    """以年化波動率分三級（白話版用）：< 8% 低、< 20% 中、其餘高。"""
    if vol != vol:
        return "—"
    return "低" if vol < 0.08 else ("中" if vol < 0.20 else "高")


def plain_summary(master: pd.DataFrame, nav_hist: pd.DataFrame, amount: float = 100.0) -> pd.DataFrame:
    """給一般投資人看的白話摘要：期初投入 amount，期末變多少、途中最低剩多少、最大跌幅、風險等級。"""
    rows = {}
    for fid in nav_hist.columns:
        nav = nav_hist[fid]
        growth = nav / nav.iloc[0]
        vol = annualized_volatility(daily_returns(nav).iloc[1:])
        rows[fid] = {
            "name": master.loc[fid, "name"],
            "category": master.loc[fid, "category"],
            "scenario": master.loc[fid, "scenario_type"],
            "expense": master.loc[fid, "expense_ratio"],
            "end_value": amount * growth.iloc[-1],
            "total_return": growth.iloc[-1] - 1,
            "low_value": amount * growth.min(),
            "low_date": growth.idxmin(),
            "high_value": amount * growth.max(),
            "max_drawdown": max_drawdown(nav),
            "volatility": vol,
            "risk": risk_level(vol),
            "r12": period_return(nav, config.MOMENTUM_WINDOWS["12M"]),
        }
    return pd.DataFrame.from_dict(rows, orient="index")
