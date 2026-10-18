"""分析服務：串接策略計算、回測與資料庫儲存。UI 只呼叫這一層。"""
from __future__ import annotations

from functools import partial

import pandas as pd

import config
from backtest.engine import BacktestResult, run_backtest, signal_indices
from backtest.metrics import compute_metrics
from database import repository as repo
from strategies import momentum, moving_average, multi_factor

STRATEGY_LABELS = {
    "momentum": "動能策略",
    "moving_average": "均線策略",
    "multi_factor": "多因子評分",
    "benchmark": "等權基準",
}


def eval_date_options(nav_wide: pd.DataFrame) -> list[pd.Timestamp]:
    """可選評估日：每個月底（索引 ≥ 252）＋ 最後一個交易日。"""
    dates = nav_wide.index
    opts = [dates[i] for i in signal_indices(dates)]
    if dates[-1] not in opts:
        opts.append(dates[-1])
    return opts


def strategy_params(strategy_id: str, mom_w: dict | None = None, fac_w: dict | None = None) -> dict:
    """完整記錄策略參數（寫入 strategy_config）。"""
    base = dict(cost_rate=config.COST_RATE, top_n=config.TOP_N, initial_capital=config.INITIAL_CAPITAL)
    if strategy_id == "momentum":
        return dict(base, weights=mom_w or config.DEFAULT_MOMENTUM_WEIGHTS, windows=config.MOMENTUM_WINDOWS)
    if strategy_id == "moving_average":
        return dict(base, sma_short=config.SMA_SHORT, sma_long=config.SMA_LONG)
    if strategy_id == "multi_factor":
        return dict(base, weights=fac_w or config.DEFAULT_FACTOR_WEIGHTS, window=config.FACTOR_WINDOW,
                    risk_free=config.RISK_FREE)
    return base


def _equal_all(nav_hist: pd.DataFrame) -> dict[str, float]:
    cols = list(nav_hist.columns)
    return {f: 1 / len(cols) for f in cols}


def selector_for(strategy_id: str, expense: pd.Series, mom_w: dict | None = None, fac_w: dict | None = None):
    if strategy_id == "momentum":
        return partial(momentum.select_top, weights=mom_w)
    if strategy_id == "moving_average":
        return moving_average.select_bull
    if strategy_id == "multi_factor":
        return lambda h: multi_factor.select_top(h, expense, fac_w)
    if strategy_id == "benchmark":
        return _equal_all
    raise KeyError(strategy_id)


def run_strategy_backtest(nav_wide: pd.DataFrame, expense: pd.Series, strategy_id: str,
                          mom_w: dict | None = None, fac_w: dict | None = None) -> tuple[BacktestResult, dict]:
    params = strategy_params(strategy_id, mom_w, fac_w)
    res = run_backtest(nav_wide, selector_for(strategy_id, expense, mom_w, fac_w), params=params)
    return res, compute_metrics(res.daily["equity"], res.trades)


def run_all_backtests(nav_wide: pd.DataFrame, expense: pd.Series, mom_w: dict | None = None,
                      fac_w: dict | None = None) -> dict[str, tuple[BacktestResult, dict]]:
    return {sid: run_strategy_backtest(nav_wide, expense, sid, mom_w, fac_w) for sid in STRATEGY_LABELS}


def save_backtests(conn, results: dict[str, tuple[BacktestResult, dict]]) -> dict[str, int]:
    run_ids = {}
    for sid, (res, metrics) in results.items():
        cid = repo.get_or_create_config(conn, sid, res.params)
        run_ids[sid] = repo.save_backtest(conn, sid, cid, config.COST_RATE, res.daily, res.trades, metrics)
    return run_ids


def save_strategy_snapshot(conn, strategy_id: str, params: dict, eval_date: pd.Timestamp,
                           results: pd.DataFrame) -> tuple[int, int]:
    cid = repo.get_or_create_config(conn, strategy_id, params)
    n = repo.save_strategy_results(conn, cid, strategy_id, eval_date.strftime("%Y-%m-%d"), results)
    return cid, n


def fund_verdict(fid: str, mom: pd.DataFrame, ma: pd.DataFrame, mf: pd.DataFrame) -> list[str]:
    """把三策略結果轉成可讀的說明句。"""
    out = []
    n = len(mom)
    m = mom.loc[fid]
    if pd.notna(m["score"]):
        out.append(f"動能分數 {m['score']:.2%}，排名第 {int(m['rank'])}/{n}；貢獻最大的是 {m['top_driver']} 報酬。")
    else:
        out.append("動能：資料不足（需至少 253 個交易日）。")
    a = ma.loc[fid]
    ev = f"，最近一次事件為 {a['last_event_date']:%Y-%m-%d} 的{a['last_event']}" if a["last_event"] else "，期間內無交叉事件"
    out.append(f"均線狀態：{a['state']}（NAV 相對 SMA200 {a['gap_pct']:+.2%}）{ev}。")
    f = mf.loc[fid]
    if pd.notna(f["score"]):
        strongest = max(config.FACTORS, key=lambda k: f[f"s_{k}"])
        weakest = min(config.FACTORS, key=lambda k: f[f"s_{k}"])
        out.append(f"多因子總分 {f['score']:.1f}，排名第 {int(f['rank'])}/{n}；最強因子為"
                   f"{config.FACTORS[strongest][0]}（{f[f's_{strongest}']:.0f} 分），最弱為"
                   f"{config.FACTORS[weakest][0]}（{f[f's_{weakest}']:.0f} 分）。")
    return out
